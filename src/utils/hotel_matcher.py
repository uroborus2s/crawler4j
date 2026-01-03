"""酒店名称匹配工具模块。

实现 Jaro-Winkler 相似度算法和酒店名称匹配逻辑，
移植自 content.js 中的 findApiBysearchHotels 函数。
"""

import re
from dataclasses import dataclass

from src.utils.logger import logger


@dataclass
class HotelMatch:
    """酒店匹配结果。"""
    hotel_id: int
    hotel_name: str
    url: str
    similarity: float
    match_type: str  # 'exact_same_city', 'similar_same_city', 'exact_cross_city', 'similar_cross_city'


class HotelMatcher:
    """酒店名称匹配器。
    
    实现4级匹配策略：
    1. 同城精确匹配
    2. 同城相似匹配（分店加权）
    3. 跨城精确匹配
    4. 跨城相似匹配（分店加权）
    """
    
    # 通用酒店词汇（用于提取主体名称）
    HOTEL_KEYWORDS = re.compile(r'酒店|宾馆|公寓|民宿|客栈|饭店')
    
    # 括号模式（用于提取分店信息）
    BRACKET_PATTERN = re.compile(r'[\s]*[\(\（].*?[\)\）]')
    
    @staticmethod
    def to_half_width(s: str) -> str:
        """全角字符转半角。
        
        Args:
            s: 输入字符串
            
        Returns:
            转换后的半角字符串
        """
        result = []
        for char in s:
            code = ord(char)
            # 全角字符范围 FF01-FF5E 转换为半角 21-7E
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 全角空格转半角
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(char)
        return ''.join(result)
    
    @classmethod
    def extract_main_name(cls, s: str) -> str:
        """提取酒店主体名称，去除括号内分店信息和通用词汇。
        
        Args:
            s: 酒店全称
            
        Returns:
            酒店主体名称
        """
        # 去掉括号内信息
        result = cls.BRACKET_PATTERN.sub('', s)
        # 去掉通用词汇
        result = cls.HOTEL_KEYWORDS.sub('', result)
        return result.strip()
    
    @classmethod
    def normalize(cls, s: str) -> str:
        """标准化字符串：全角转半角，去空格，小写化。
        
        Args:
            s: 待处理字符串
            
        Returns:
            标准化后的字符串
        """
        s = cls.to_half_width(s)
        s = re.sub(r'\s+', '', s)
        return s.lower()
    
    @classmethod
    def jaro_winkler_similarity(cls, s1: str, s2: str) -> float:
        """计算 Jaro-Winkler 相似度。
        
        Args:
            s1: 字符串1
            s2: 字符串2
            
        Returns:
            相似度分数 (0.0 到 1.0)
        """
        s1 = cls.normalize(s1)
        s2 = cls.normalize(s2)
        
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # 计算匹配窗口
        m = max(len(s1), len(s2))
        match_distance = max(0, m // 2 - 1)
        
        s1_matches = [False] * len(s1)
        s2_matches = [False] * len(s2)
        
        matches = 0
        transpositions = 0
        
        # 查找匹配字符
        for i in range(len(s1)):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len(s2))
            
            for j in range(start, end):
                if not s2_matches[j] and s1[i] == s2[j]:
                    s1_matches[i] = True
                    s2_matches[j] = True
                    matches += 1
                    break
        
        if matches == 0:
            return 0.0
        
        # 计算换位次数
        k = 0
        for i in range(len(s1)):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
        
        transpositions //= 2
        
        # 计算 Jaro 相似度
        jaro = (
            matches / len(s1) +
            matches / len(s2) +
            (matches - transpositions) / matches
        ) / 3
        
        # Winkler 前缀加权
        prefix = 0
        for i in range(min(4, len(s1), len(s2))):
            if s1[i] == s2[i]:
                prefix += 1
            else:
                break
        
        jaro += prefix * 0.1 * (1 - jaro)

        return jaro

    @classmethod
    def calculate_hotel_score(
        cls,
        hotel_name: str,
        keyword_main: str,
        keyword_branch: str
    ) -> float:
        """计算酒店匹配分数（使用分店加权策略）。

        Args:
            hotel_name: 搜索结果中的酒店名称
            keyword_main: 关键词主体名称
            keyword_branch: 关键词分店部分

        Returns:
            匹配分数 (0.0 到 1.0)
        """
        hotel_half = cls.to_half_width(hotel_name)
        hotel_main = cls.extract_main_name(hotel_half)

        # 主体名称必须相同
        if hotel_main != keyword_main:
            return 0.0

        hotel_branch = hotel_half.replace(hotel_main, '').strip()

        if hotel_branch:
            # 有分店信息时：主体权重0.7，分店权重0.3
            branch_sim = cls.jaro_winkler_similarity(hotel_branch, keyword_branch) if keyword_branch else 0.0
            score = 0.7 * 1.0 + 0.3 * branch_sim
        else:
            # 无分店信息时：直接比较主体相似度
            score = cls.jaro_winkler_similarity(hotel_main, keyword_main)

        return score

    @classmethod
    def match_hotels(
        cls,
        hotels: list[dict],
        keyword: str,
        city_name: str | None = None,
        similarity_threshold: float = 0.90
    ) -> HotelMatch | None:
        """在酒店列表中查找匹配的酒店。

        实现4级匹配策略：
        1. 同城精确匹配
        2. 同城相似匹配（分店加权，阈值 > similarity_threshold）
        3. 跨城精确匹配
        4. 跨城相似匹配（分店加权，阈值 > similarity_threshold）

        Args:
            hotels: 酒店列表，每个酒店需包含 'word'/'hotelName', 'id'/'hotelId', 'cityName' 等字段
            keyword: 搜索关键词（酒店名称）
            city_name: 目标城市名称（可选）
            similarity_threshold: 相似度阈值，默认 0.90 (90%)

        Returns:
            匹配到的酒店信息，如无匹配返回 None
        """
        if not hotels:
            return None

        # 预处理关键词
        keyword_half = cls.to_half_width(keyword)
        keyword_main = cls.extract_main_name(keyword_half)
        keyword_branch = keyword_half.replace(keyword_main, '').strip()

        # 标准化城市名称
        normalized_city = cls.to_half_width(city_name).strip().lower() if city_name else None

        # 分离同城和跨城酒店
        city_hotels = []
        all_hotels = []

        for hotel in hotels:
            # 兼容不同的字段名
            hotel_name = hotel.get('word') or hotel.get('hotelName') or ''
            hotel_id = hotel.get('id') or hotel.get('hotelId') or 0
            hotel_city = hotel.get('cityName') or ''
            hotel_url = hotel.get('url') or f"https://hotels.ctrip.com/hotels/{hotel_id}.html"

            if not hotel_name or not hotel_id:
                continue

            hotel_info = {
                'name': hotel_name,
                'id': int(hotel_id) if isinstance(hotel_id, str) else hotel_id,
                'city': hotel_city,
                'url': hotel_url
            }
            all_hotels.append(hotel_info)

            # 判断是否同城
            if normalized_city and hotel_city:
                normalized_hotel_city = cls.to_half_width(hotel_city).strip().lower()
                if (normalized_hotel_city in normalized_city or
                    normalized_city in normalized_hotel_city):
                    city_hotels.append(hotel_info)

        # 1. 同城精确匹配
        for hotel in city_hotels:
            if cls.to_half_width(hotel['name']) == keyword_half:
                logger.debug(f"同城精确匹配: {hotel['name']}")
                return HotelMatch(
                    hotel_id=hotel['id'],
                    hotel_name=hotel['name'],
                    url=hotel['url'],
                    similarity=1.0,
                    match_type='exact_same_city'
                )

        # 2. 同城相似匹配（分店加权）
        best_city_hotel = None
        best_city_score = 0.0

        for hotel in city_hotels:
            score = cls.calculate_hotel_score(
                hotel['name'], keyword_main, keyword_branch
            )
            if score > best_city_score:
                best_city_score = score
                best_city_hotel = hotel

        if best_city_hotel and best_city_score >= similarity_threshold:
            logger.debug(f"同城相似匹配: {best_city_hotel['name']} (分数: {best_city_score:.2%})")
            return HotelMatch(
                hotel_id=best_city_hotel['id'],
                hotel_name=best_city_hotel['name'],
                url=best_city_hotel['url'],
                similarity=best_city_score,
                match_type='similar_same_city'
            )

        # 3. 跨城精确匹配
        for hotel in all_hotels:
            if cls.to_half_width(hotel['name']) == keyword_half:
                logger.debug(f"跨城精确匹配: {hotel['name']}")
                return HotelMatch(
                    hotel_id=hotel['id'],
                    hotel_name=hotel['name'],
                    url=hotel['url'],
                    similarity=1.0,
                    match_type='exact_cross_city'
                )

        # 4. 跨城相似匹配（分店加权）
        best_cross_hotel = None
        best_cross_score = 0.0

        for hotel in all_hotels:
            score = cls.calculate_hotel_score(
                hotel['name'], keyword_main, keyword_branch
            )
            if score > best_cross_score:
                best_cross_score = score
                best_cross_hotel = hotel

        if best_cross_hotel and best_cross_score >= similarity_threshold:
            logger.debug(f"跨城相似匹配: {best_cross_hotel['name']} (分数: {best_cross_score:.2%})")
            return HotelMatch(
                hotel_id=best_cross_hotel['id'],
                hotel_name=best_cross_hotel['name'],
                url=best_cross_hotel['url'],
                similarity=best_cross_score,
                match_type='similar_cross_city'
            )

        # 无匹配
        logger.debug(f"未找到匹配酒店，最高分数: {max(best_city_score, best_cross_score):.2%}")
        return None

