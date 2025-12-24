// 劳保保助手插件优化版本 - 稳定执行架构 V3.0 (增强 UI)
(function() {
    'use strict';

    // ----------------------------------------------------
    // 兼容性降级：从您原文件提取 (确保 AbortController 可用)
    // ----------------------------------------------------

    function createAbortControllerFallback() {
        // ... (省略 AbortController 降级代码，与上一步相同)
        function AbortSignal() {
            this.aborted = false;
            this._listeners = [];
        }

        AbortSignal.prototype.addEventListener = function(type, listener) {
            if (type === 'abort') {
                this._listeners.push(listener);
            }
        };

        AbortSignal.prototype.removeEventListener = function(type, listener) {
             if (type === 'abort') {
                var index = this._listeners.indexOf(listener);
                if (index > -1) {
                    this._listeners.splice(index, 1);
                }
            }
        };

        AbortSignal.prototype._fire = function() {
            this.aborted = true;
            for (var i = 0; i < this._listeners.length; i++) {
                setTimeout(this._listeners[i].bind(this), 0);
            }
            this._listeners = [];
        };

        function AbortController() {
            this.signal = new AbortSignal();
        }

        AbortController.prototype.abort = function() {
            this.signal._fire();
        };

        return AbortController;
    }

    if (typeof window.AbortController === 'undefined') {
        window.AbortController = createAbortControllerFallback();
    }

    var LOG_LEVEL = {
        INFO: 'info',
        WARN: 'warn',
        ERROR: 'error'
    };

    var cityList = [{"id":2,"name":"上海","nameEn":"Shanghai"},{"id":1,"name":"北京","nameEn":"Beijing"},{"id":32,"name":"广州","nameEn":"Guangzhou"},{"id":43,"name":"三亚","nameEn":"Sanya"},{"id":17,"name":"杭州","nameEn":"Hangzhou"},{"id":28,"name":"成都","nameEn":"Chengdu"},{"id":12,"name":"南京","nameEn":"Nanjing"},{"id":4,"name":"重庆","nameEn":"Chongqing"},{"id":30,"name":"深圳","nameEn":"Shenzhen"},{"id":25,"name":"厦门","nameEn":"Xiamen"},{"id":10,"name":"西安","nameEn":"Xi'an"},{"id":477,"name":"武汉","nameEn":"Wuhan"},{"id":34,"name":"昆明","nameEn":"Kunming"},{"id":206,"name":"长沙","nameEn":"Changsha"},{"id":14,"name":"苏州","nameEn":"Suzhou"},{"id":5,"name":"哈尔滨","nameEn":"Harbin"},{"id":59,"name":"澳门","nameEn":"Macau"},{"id":3,"name":"天津","nameEn":"Tianjin"},{"id":144,"name":"济南","nameEn":"Jinan"},{"id":559,"name":"郑州","nameEn":"Zhengzhou"},{"id":31,"name":"珠海","nameEn":"Zhuhai"},{"id":7,"name":"青岛","nameEn":"Qingdao"},{"id":278,"name":"合肥","nameEn":"Hefei"},{"id":376,"name":"南昌","nameEn":"Nanchang"},{"id":258,"name":"福州","nameEn":"Fuzhou"},{"id":451,"name":"沈阳","nameEn":"Shenyang"},{"id":36,"name":"大理市","nameEn":"Dali"},{"id":38,"name":"贵阳","nameEn":"Guiyang"},{"id":428,"name":"石家庄","nameEn":"Shijiazhuang"},{"id":58,"name":"香港","nameEn":"Hong Kong"},{"id":375,"name":"宁波","nameEn":"Ningbo"},{"id":13,"name":"无锡","nameEn":"Wuxi"},{"id":380,"name":"南宁","nameEn":"Nanning"},{"id":158,"name":"长春","nameEn":"Changchun"},{"id":105,"name":"太原","nameEn":"Taiyuan"},{"id":251,"name":"佛山","nameEn":"Foshan"},{"id":42,"name":"海口","nameEn":"Haikou"},{"id":6,"name":"大连","nameEn":"Dalian"},{"id":100,"name":"兰州","nameEn":"Lanzhou"},{"id":37,"name":"丽江","nameEn":"Lijiang"},{"id":19,"name":"舟山","nameEn":"Zhoushan"},{"id":189,"name":"北海","nameEn":"Beihai"},{"id":223,"name":"东莞","nameEn":"Dongguan"},{"id":15,"name":"扬州","nameEn":"Yangzhou"},{"id":33,"name":"桂林","nameEn":"Guilin"},{"id":39,"name":"乌鲁木齐","nameEn":"Urumqi"},{"id":1819,"name":"腾冲","nameEn":"Tengchong"},{"id":213,"name":"常州","nameEn":"Changzhou"},{"id":309,"name":"景洪","nameEn":"Jinghong"},{"id":23,"name":"黄山","nameEn":"Huangshan"},{"id":491,"name":"温州","nameEn":"Wenzhou"},{"id":580,"name":"桐乡","nameEn":"Tongxiang"},{"id":512,"name":"徐州","nameEn":"Xuzhou"},{"id":103,"name":"呼和浩特","nameEn":"Hohhot"},{"id":871,"name":"阳朔","nameEn":"Yangshuo"},{"id":83,"name":"昆山","nameEn":"Kunshan"},{"id":533,"name":"烟台","nameEn":"Yantai"},{"id":350,"name":"洛阳","nameEn":"Luoyang"},{"id":22,"name":"绍兴","nameEn":"Shaoxing"},{"id":299,"name":"惠州","nameEn":"Huizhou"},{"id":547,"name":"湛江","nameEn":"Zhanjiang"},{"id":95,"name":"峨眉山","nameEn":"Emeishan"},{"id":553,"name":"中山","nameEn":"Zhongshan"},{"id":985,"name":"曲靖","nameEn":"Qujing"},{"id":20,"name":"淳安","nameEn":"Chun'an"},{"id":185,"name":"保定","nameEn":"Baoding"},{"id":550,"name":"张家口","nameEn":"Zhangjiakou"},{"id":1367,"name":"德清","nameEn":"Deqing"},{"id":447,"name":"汕头","nameEn":"Shantou"},{"id":99,"name":"银川","nameEn":"Yinchuan"},{"id":308,"name":"金华","nameEn":"Jinhua"},{"id":406,"name":"泉州","nameEn":"Quanzhou"},{"id":111,"name":"咸阳","nameEn":"Xianyang"},{"id":1358,"name":"溧阳","nameEn":"Liyang"},{"id":186,"name":"玉溪","nameEn":"Yuxi"},{"id":86,"name":"湖州","nameEn":"Huzhou"},{"id":41,"name":"拉萨","nameEn":"Lhasa"},{"id":124,"name":"西宁","nameEn":"Xining"},{"id":82,"name":"南通","nameEn":"Nantong"},{"id":454,"name":"泰安","nameEn":"Taian"},{"id":331,"name":"开封","nameEn":"Kaifeng"},{"id":94,"name":"都江堰","nameEn":"Dujiangyan"},{"id":542,"name":"淄博","nameEn":"Zibo"},{"id":27,"name":"张家界","nameEn":"Zhangjiajie"},{"id":21421,"name":"长沙县","nameEn":"Changsha County"},{"id":596,"name":"嘉善","nameEn":"Jiashan"},{"id":536,"name":"义乌","nameEn":"Yiwu"},{"id":21976,"name":"惠东","nameEn":"Huidong"},{"id":659,"name":"安吉","nameEn":"Anji"},{"id":475,"name":"潍坊","nameEn":"Weifang"},{"id":489,"name":"婺源","nameEn":"Wuyuan"},{"id":571,"name":"嘉兴","nameEn":"Jiaxing"},{"id":147,"name":"秦皇岛","nameEn":"Qinhuangdao"},{"id":478,"name":"芜湖","nameEn":"Wuhu"},{"id":370,"name":"绵阳","nameEn":"Mianyang"},{"id":1666,"name":"海林","nameEn":"Hailin"},{"id":1200,"name":"盐城","nameEn":"Yancheng"},{"id":318,"name":"济宁","nameEn":"Jining"},{"id":16,"name":"镇江","nameEn":"Zhenjiang"},{"id":159,"name":"吉林市","nameEn":"Jilin"},{"id":617,"name":"台北","nameEn":"Taipei"},{"id":1453,"name":"晋中","nameEn":"Jinzhong"},{"id":1161,"name":"宁蒗","nameEn":"Ninglang"},{"id":354,"name":"柳州","nameEn":"Liuzhou"},{"id":215,"name":"潮州","nameEn":"Chaozhou"},{"id":403,"name":"黟县","nameEn":"Yi County"},{"id":468,"name":"唐山","nameEn":"Tangshan"},{"id":268,"name":"赣州","nameEn":"Ganzhou"},{"id":21075,"name":"龙门","nameEn":"Longmen"},{"id":26,"name":"武夷山","nameEn":"Wuyishan"},{"id":345,"name":"乐山","nameEn":"Leshan"},{"id":578,"name":"台州","nameEn":"Taizhou"},{"id":569,"name":"临沂","nameEn":"Linyi"},{"id":199,"name":"白山","nameEn":"Baishan"},{"id":45,"name":"万宁","nameEn":"Wanning"},{"id":552,"name":"肇庆","nameEn":"Zhaoqing"},{"id":494,"name":"西昌","nameEn":"Xichang"},{"id":1106,"name":"日照","nameEn":"Rizhao"},{"id":515,"name":"宜昌","nameEn":"Yichang"},{"id":514,"name":"宜宾","nameEn":"Yibin"},{"id":7751,"name":"理县","nameEn":"Li County"},{"id":479,"name":"威海","nameEn":"Weihai"},{"id":866,"name":"凤凰","nameEn":"Fenghuang"},{"id":1422,"name":"清远","nameEn":"Qingyuan"},{"id":340,"name":"廊坊","nameEn":"Langfang"},{"id":316,"name":"江门","nameEn":"Jiangmen"},{"id":579,"name":"泰州","nameEn":"Taizhou"},{"id":558,"name":"遵义","nameEn":"Zunyi"},{"id":297,"name":"衡阳","nameEn":"Hengyang"},{"id":7716,"name":"大邑","nameEn":"Dayi"},{"id":755,"name":"东阳","nameEn":"Dongyang"},{"id":20932,"name":"青阳","nameEn":"Qingyang"},{"id":560,"name":"漳州","nameEn":"Zhangzhou"},{"id":692,"name":"阳江","nameEn":"Yangjiang"},{"id":353,"name":"连云港","nameEn":"Lianyungang"},{"id":136,"name":"大同","nameEn":"Datong"},{"id":577,"name":"淮安","nameEn":"Huai'an"},{"id":496,"name":"襄阳","nameEn":"Xiangyang"},{"id":518,"name":"宜春","nameEn":"Yichun"},{"id":540,"name":"余姚","nameEn":"Yuyao"},{"id":182,"name":"蚌埠","nameEn":"Bengbu"},{"id":1803,"name":"晋江","nameEn":"Jinjiang"},{"id":377,"name":"南充","nameEn":"Nanchong"},{"id":1208,"name":"慈溪","nameEn":"Cixi"},{"id":422,"name":"韶关","nameEn":"Shaoguan"},{"id":275,"name":"邯郸","nameEn":"Handan"},{"id":21194,"name":"中牟","nameEn":"Zhongmou"},{"id":537,"name":"宜兴","nameEn":"Yixing"},{"id":601,"name":"株洲","nameEn":"Zhuzhou"},{"id":96,"name":"常熟","nameEn":"Changshu"},{"id":328,"name":"荆州","nameEn":"Jingzhou"},{"id":621,"name":"张家港","nameEn":"Zhangjiagang"},{"id":305,"name":"景德镇","nameEn":"Jingdezhen"},{"id":24,"name":"九江","nameEn":"Jiujiang"},{"id":52,"name":"琼海","nameEn":"Qionghai"},{"id":20919,"name":"澄江","nameEn":"Chengjiang"},{"id":21959,"name":"南昌县","nameEn":"Nanchang County"},{"id":290,"name":"衡水","nameEn":"Hengshui"},{"id":693,"name":"河源","nameEn":"Heyuan"},{"id":216,"name":"沧州","nameEn":"Cangzhou"},{"id":660,"name":"香格里拉","nameEn":"Shangri-La"},{"id":355,"name":"泸州","nameEn":"Luzhou"},{"id":129,"name":"汉中","nameEn":"Hanzhong"},{"id":55,"name":"陵水","nameEn":"Lingshui"},{"id":539,"name":"岳阳","nameEn":"Yueyang"},{"id":411,"name":"上饶","nameEn":"Shangrao"},{"id":460,"name":"桐庐","nameEn":"Tonglu"},{"id":507,"name":"新乡","nameEn":"Xinxiang"},{"id":452,"name":"十堰","nameEn":"Shiyan"},{"id":325,"name":"江阴","nameEn":"Jiangyin"},{"id":614,"name":"枣庄","nameEn":"Zaozhuang"},{"id":407,"name":"衢州","nameEn":"Quzhou"},{"id":22001,"name":"仁寿","nameEn":"Renshou"},{"id":346,"name":"丽水","nameEn":"Lishui"},{"id":1105,"name":"茂名","nameEn":"Maoming"},{"id":1074,"name":"菏泽","nameEn":"Heze"},{"id":257,"name":"阜阳","nameEn":"Fuyang"},{"id":21670,"name":"南雄","nameEn":"Nanxiong"},{"id":141,"name":"包头","nameEn":"Baotou"},{"id":1071,"name":"聊城","nameEn":"Liaocheng"},{"id":112,"name":"宝鸡","nameEn":"Baoji"},{"id":667,"name":"莆田","nameEn":"Putian"},{"id":327,"name":"锦州","nameEn":"Jinzhou"},{"id":1370,"name":"德州","nameEn":"Dezhou"},{"id":458,"name":"通辽","nameEn":"Tongliao"},{"id":84,"name":"海宁","nameEn":"Haining"},{"id":143,"name":"曲阜","nameEn":"Qufu"},{"id":3221,"name":"周口","nameEn":"Zhoukou"},{"id":385,"name":"南阳","nameEn":"Nanyang"},{"id":510,"name":"信阳","nameEn":"Xinyang"},{"id":441,"name":"商丘","nameEn":"Shangqiu"},{"id":1097,"name":"攀枝花","nameEn":"Panzhihua"},{"id":236,"name":"东营","nameEn":"Dongying"},{"id":2966,"name":"尚志","nameEn":"Shangzhi"},{"id":348,"name":"龙岩","nameEn":"Longyan"},{"id":202,"name":"赤峰","nameEn":"Chifeng"},{"id":221,"name":"丹东","nameEn":"Dandong"},{"id":104,"name":"平遥","nameEn":"Pingyao"},{"id":179,"name":"安顺","nameEn":"Anshun"},{"id":201,"name":"常德","nameEn":"Changde"},{"id":1107,"name":"长兴","nameEn":"Changxing"},{"id":3277,"name":"雅安","nameEn":"Ya'an"},{"id":44,"name":"文昌","nameEn":"Wenchang"},{"id":20893,"name":"恩施市","nameEn":"Enshishi"},{"id":234,"name":"达州","nameEn":"Dazhou"},{"id":21902,"name":"闽侯","nameEn":"Minhou"},{"id":612,"name":"郴州","nameEn":"Chenzhou"},{"id":732,"name":"乐清","nameEn":"Yueqing"},{"id":1300,"name":"营口","nameEn":"Yingkou"},{"id":527,"name":"榆林","nameEn":"Yulin"},{"id":1993,"name":"正定","nameEn":"Zhengding"},{"id":21286,"name":"雷山","nameEn":"Leishan"},{"id":937,"name":"咸宁","nameEn":"Xianning"},{"id":523,"name":"延吉","nameEn":"Yanji"},{"id":177,"name":"安庆","nameEn":"Anqing"},{"id":1093,"name":"焦作","nameEn":"Jiaozuo"},{"id":1024,"name":"马鞍山","nameEn":"Ma'anshan"},{"id":378,"name":"宁德","nameEn":"Ningde"},{"id":884,"name":"英德","nameEn":"Yingde"},{"id":110,"name":"延安","nameEn":"Yan'an"},{"id":3053,"name":"梅州","nameEn":"Meizhou"},{"id":1201,"name":"宁海","nameEn":"Ninghai"},{"id":548,"name":"诸暨","nameEn":"Zhuji"},{"id":181,"name":"安阳","nameEn":"Anyang"},{"id":21939,"name":"南澳","nameEn":"Nanao"},{"id":267,"name":"广元","nameEn":"Guangyuan"},{"id":412,"name":"瑞丽","nameEn":"Ruili"},{"id":4243,"name":"弥勒","nameEn":"Mile"},{"id":1454,"name":"济源","nameEn":"Jiyuan"},{"id":1094,"name":"许昌","nameEn":"Xuchang"},{"id":1472,"name":"宿迁","nameEn":"Suqian"},{"id":1140,"name":"百色","nameEn":"Baise"},{"id":1708,"name":"荔波","nameEn":"Libo"}];
    const GLOBAL_PARAMS = {
      // 账号相关
      cityList: [{"id":2,"name":"上海","nameEn":"Shanghai"},{"id":1,"name":"北京","nameEn":"Beijing"},{"id":32,"name":"广州","nameEn":"Guangzhou"},{"id":43,"name":"三亚","nameEn":"Sanya"},{"id":17,"name":"杭州","nameEn":"Hangzhou"},{"id":28,"name":"成都","nameEn":"Chengdu"},{"id":12,"name":"南京","nameEn":"Nanjing"},{"id":4,"name":"重庆","nameEn":"Chongqing"},{"id":30,"name":"深圳","nameEn":"Shenzhen"},{"id":25,"name":"厦门","nameEn":"Xiamen"},{"id":10,"name":"西安","nameEn":"Xi'an"},{"id":477,"name":"武汉","nameEn":"Wuhan"},{"id":34,"name":"昆明","nameEn":"Kunming"},{"id":206,"name":"长沙","nameEn":"Changsha"},{"id":14,"name":"苏州","nameEn":"Suzhou"},{"id":5,"name":"哈尔滨","nameEn":"Harbin"},{"id":59,"name":"澳门","nameEn":"Macau"},{"id":3,"name":"天津","nameEn":"Tianjin"},{"id":144,"name":"济南","nameEn":"Jinan"},{"id":559,"name":"郑州","nameEn":"Zhengzhou"},{"id":31,"name":"珠海","nameEn":"Zhuhai"},{"id":7,"name":"青岛","nameEn":"Qingdao"},{"id":278,"name":"合肥","nameEn":"Hefei"},{"id":376,"name":"南昌","nameEn":"Nanchang"},{"id":258,"name":"福州","nameEn":"Fuzhou"},{"id":451,"name":"沈阳","nameEn":"Shenyang"},{"id":36,"name":"大理市","nameEn":"Dali"},{"id":38,"name":"贵阳","nameEn":"Guiyang"},{"id":428,"name":"石家庄","nameEn":"Shijiazhuang"},{"id":58,"name":"香港","nameEn":"Hong Kong"},{"id":375,"name":"宁波","nameEn":"Ningbo"},{"id":13,"name":"无锡","nameEn":"Wuxi"},{"id":380,"name":"南宁","nameEn":"Nanning"},{"id":158,"name":"长春","nameEn":"Changchun"},{"id":105,"name":"太原","nameEn":"Taiyuan"},{"id":251,"name":"佛山","nameEn":"Foshan"},{"id":42,"name":"海口","nameEn":"Haikou"},{"id":6,"name":"大连","nameEn":"Dalian"},{"id":100,"name":"兰州","nameEn":"Lanzhou"},{"id":37,"name":"丽江","nameEn":"Lijiang"},{"id":19,"name":"舟山","nameEn":"Zhoushan"},{"id":189,"name":"北海","nameEn":"Beihai"},{"id":223,"name":"东莞","nameEn":"Dongguan"},{"id":15,"name":"扬州","nameEn":"Yangzhou"},{"id":33,"name":"桂林","nameEn":"Guilin"},{"id":39,"name":"乌鲁木齐","nameEn":"Urumqi"},{"id":1819,"name":"腾冲","nameEn":"Tengchong"},{"id":213,"name":"常州","nameEn":"Changzhou"},{"id":309,"name":"景洪","nameEn":"Jinghong"},{"id":23,"name":"黄山","nameEn":"Huangshan"},{"id":491,"name":"温州","nameEn":"Wenzhou"},{"id":580,"name":"桐乡","nameEn":"Tongxiang"},{"id":512,"name":"徐州","nameEn":"Xuzhou"},{"id":103,"name":"呼和浩特","nameEn":"Hohhot"},{"id":871,"name":"阳朔","nameEn":"Yangshuo"},{"id":83,"name":"昆山","nameEn":"Kunshan"},{"id":533,"name":"烟台","nameEn":"Yantai"},{"id":350,"name":"洛阳","nameEn":"Luoyang"},{"id":22,"name":"绍兴","nameEn":"Shaoxing"},{"id":299,"name":"惠州","nameEn":"Huizhou"},{"id":547,"name":"湛江","nameEn":"Zhanjiang"},{"id":95,"name":"峨眉山","nameEn":"Emeishan"},{"id":553,"name":"中山","nameEn":"Zhongshan"},{"id":985,"name":"曲靖","nameEn":"Qujing"},{"id":20,"name":"淳安","nameEn":"Chun'an"},{"id":185,"name":"保定","nameEn":"Baoding"},{"id":550,"name":"张家口","nameEn":"Zhangjiakou"},{"id":1367,"name":"德清","nameEn":"Deqing"},{"id":447,"name":"汕头","nameEn":"Shantou"},{"id":99,"name":"银川","nameEn":"Yinchuan"},{"id":308,"name":"金华","nameEn":"Jinhua"},{"id":406,"name":"泉州","nameEn":"Quanzhou"},{"id":111,"name":"咸阳","nameEn":"Xianyang"},{"id":1358,"name":"溧阳","nameEn":"Liyang"},{"id":186,"name":"玉溪","nameEn":"Yuxi"},{"id":86,"name":"湖州","nameEn":"Huzhou"},{"id":41,"name":"拉萨","nameEn":"Lhasa"},{"id":124,"name":"西宁","nameEn":"Xining"},{"id":82,"name":"南通","nameEn":"Nantong"},{"id":454,"name":"泰安","nameEn":"Taian"},{"id":331,"name":"开封","nameEn":"Kaifeng"},{"id":94,"name":"都江堰","nameEn":"Dujiangyan"},{"id":542,"name":"淄博","nameEn":"Zibo"},{"id":27,"name":"张家界","nameEn":"Zhangjiajie"},{"id":21421,"name":"长沙县","nameEn":"Changsha County"},{"id":596,"name":"嘉善","nameEn":"Jiashan"},{"id":536,"name":"义乌","nameEn":"Yiwu"},{"id":21976,"name":"惠东","nameEn":"Huidong"},{"id":659,"name":"安吉","nameEn":"Anji"},{"id":475,"name":"潍坊","nameEn":"Weifang"},{"id":489,"name":"婺源","nameEn":"Wuyuan"},{"id":571,"name":"嘉兴","nameEn":"Jiaxing"},{"id":147,"name":"秦皇岛","nameEn":"Qinhuangdao"},{"id":478,"name":"芜湖","nameEn":"Wuhu"},{"id":370,"name":"绵阳","nameEn":"Mianyang"},{"id":1666,"name":"海林","nameEn":"Hailin"},{"id":1200,"name":"盐城","nameEn":"Yancheng"},{"id":318,"name":"济宁","nameEn":"Jining"},{"id":16,"name":"镇江","nameEn":"Zhenjiang"},{"id":159,"name":"吉林市","nameEn":"Jilin"},{"id":617,"name":"台北","nameEn":"Taipei"},{"id":1453,"name":"晋中","nameEn":"Jinzhong"},{"id":1161,"name":"宁蒗","nameEn":"Ninglang"},{"id":354,"name":"柳州","nameEn":"Liuzhou"},{"id":215,"name":"潮州","nameEn":"Chaozhou"},{"id":403,"name":"黟县","nameEn":"Yi County"},{"id":468,"name":"唐山","nameEn":"Tangshan"},{"id":268,"name":"赣州","nameEn":"Ganzhou"},{"id":21075,"name":"龙门","nameEn":"Longmen"},{"id":26,"name":"武夷山","nameEn":"Wuyishan"},{"id":345,"name":"乐山","nameEn":"Leshan"},{"id":578,"name":"台州","nameEn":"Taizhou"},{"id":569,"name":"临沂","nameEn":"Linyi"},{"id":199,"name":"白山","nameEn":"Baishan"},{"id":45,"name":"万宁","nameEn":"Wanning"},{"id":552,"name":"肇庆","nameEn":"Zhaoqing"},{"id":494,"name":"西昌","nameEn":"Xichang"},{"id":1106,"name":"日照","nameEn":"Rizhao"},{"id":515,"name":"宜昌","nameEn":"Yichang"},{"id":514,"name":"宜宾","nameEn":"Yibin"},{"id":7751,"name":"理县","nameEn":"Li County"},{"id":479,"name":"威海","nameEn":"Weihai"},{"id":866,"name":"凤凰","nameEn":"Fenghuang"},{"id":1422,"name":"清远","nameEn":"Qingyuan"},{"id":340,"name":"廊坊","nameEn":"Langfang"},{"id":316,"name":"江门","nameEn":"Jiangmen"},{"id":579,"name":"泰州","nameEn":"Taizhou"},{"id":558,"name":"遵义","nameEn":"Zunyi"},{"id":297,"name":"衡阳","nameEn":"Hengyang"},{"id":7716,"name":"大邑","nameEn":"Dayi"},{"id":755,"name":"东阳","nameEn":"Dongyang"},{"id":20932,"name":"青阳","nameEn":"Qingyang"},{"id":560,"name":"漳州","nameEn":"Zhangzhou"},{"id":692,"name":"阳江","nameEn":"Yangjiang"},{"id":353,"name":"连云港","nameEn":"Lianyungang"},{"id":136,"name":"大同","nameEn":"Datong"},{"id":577,"name":"淮安","nameEn":"Huai'an"},{"id":496,"name":"襄阳","nameEn":"Xiangyang"},{"id":518,"name":"宜春","nameEn":"Yichun"},{"id":540,"name":"余姚","nameEn":"Yuyao"},{"id":182,"name":"蚌埠","nameEn":"Bengbu"},{"id":1803,"name":"晋江","nameEn":"Jinjiang"},{"id":377,"name":"南充","nameEn":"Nanchong"},{"id":1208,"name":"慈溪","nameEn":"Cixi"},{"id":422,"name":"韶关","nameEn":"Shaoguan"},{"id":275,"name":"邯郸","nameEn":"Handan"},{"id":21194,"name":"中牟","nameEn":"Zhongmou"},{"id":537,"name":"宜兴","nameEn":"Yixing"},{"id":601,"name":"株洲","nameEn":"Zhuzhou"},{"id":96,"name":"常熟","nameEn":"Changshu"},{"id":328,"name":"荆州","nameEn":"Jingzhou"},{"id":621,"name":"张家港","nameEn":"Zhangjiagang"},{"id":305,"name":"景德镇","nameEn":"Jingdezhen"},{"id":24,"name":"九江","nameEn":"Jiujiang"},{"id":52,"name":"琼海","nameEn":"Qionghai"},{"id":20919,"name":"澄江","nameEn":"Chengjiang"},{"id":21959,"name":"南昌县","nameEn":"Nanchang County"},{"id":290,"name":"衡水","nameEn":"Hengshui"},{"id":693,"name":"河源","nameEn":"Heyuan"},{"id":216,"name":"沧州","nameEn":"Cangzhou"},{"id":660,"name":"香格里拉","nameEn":"Shangri-La"},{"id":355,"name":"泸州","nameEn":"Luzhou"},{"id":129,"name":"汉中","nameEn":"Hanzhong"},{"id":55,"name":"陵水","nameEn":"Lingshui"},{"id":539,"name":"岳阳","nameEn":"Yueyang"},{"id":411,"name":"上饶","nameEn":"Shangrao"},{"id":460,"name":"桐庐","nameEn":"Tonglu"},{"id":507,"name":"新乡","nameEn":"Xinxiang"},{"id":452,"name":"十堰","nameEn":"Shiyan"},{"id":325,"name":"江阴","nameEn":"Jiangyin"},{"id":614,"name":"枣庄","nameEn":"Zaozhuang"},{"id":407,"name":"衢州","nameEn":"Quzhou"},{"id":22001,"name":"仁寿","nameEn":"Renshou"},{"id":346,"name":"丽水","nameEn":"Lishui"},{"id":1105,"name":"茂名","nameEn":"Maoming"},{"id":1074,"name":"菏泽","nameEn":"Heze"},{"id":257,"name":"阜阳","nameEn":"Fuyang"},{"id":21670,"name":"南雄","nameEn":"Nanxiong"},{"id":141,"name":"包头","nameEn":"Baotou"},{"id":1071,"name":"聊城","nameEn":"Liaocheng"},{"id":112,"name":"宝鸡","nameEn":"Baoji"},{"id":667,"name":"莆田","nameEn":"Putian"},{"id":327,"name":"锦州","nameEn":"Jinzhou"},{"id":1370,"name":"德州","nameEn":"Dezhou"},{"id":458,"name":"通辽","nameEn":"Tongliao"},{"id":84,"name":"海宁","nameEn":"Haining"},{"id":143,"name":"曲阜","nameEn":"Qufu"},{"id":3221,"name":"周口","nameEn":"Zhoukou"},{"id":385,"name":"南阳","nameEn":"Nanyang"},{"id":510,"name":"信阳","nameEn":"Xinyang"},{"id":441,"name":"商丘","nameEn":"Shangqiu"},{"id":1097,"name":"攀枝花","nameEn":"Panzhihua"},{"id":236,"name":"东营","nameEn":"Dongying"},{"id":2966,"name":"尚志","nameEn":"Shangzhi"},{"id":348,"name":"龙岩","nameEn":"Longyan"},{"id":202,"name":"赤峰","nameEn":"Chifeng"},{"id":221,"name":"丹东","nameEn":"Dandong"},{"id":104,"name":"平遥","nameEn":"Pingyao"},{"id":179,"name":"安顺","nameEn":"Anshun"},{"id":201,"name":"常德","nameEn":"Changde"},{"id":1107,"name":"长兴","nameEn":"Changxing"},{"id":3277,"name":"雅安","nameEn":"Ya'an"},{"id":44,"name":"文昌","nameEn":"Wenchang"},{"id":20893,"name":"恩施市","nameEn":"Enshishi"},{"id":234,"name":"达州","nameEn":"Dazhou"},{"id":21902,"name":"闽侯","nameEn":"Minhou"},{"id":612,"name":"郴州","nameEn":"Chenzhou"},{"id":732,"name":"乐清","nameEn":"Yueqing"},{"id":1300,"name":"营口","nameEn":"Yingkou"},{"id":527,"name":"榆林","nameEn":"Yulin"},{"id":1993,"name":"正定","nameEn":"Zhengding"},{"id":21286,"name":"雷山","nameEn":"Leishan"},{"id":937,"name":"咸宁","nameEn":"Xianning"},{"id":523,"name":"延吉","nameEn":"Yanji"},{"id":177,"name":"安庆","nameEn":"Anqing"},{"id":1093,"name":"焦作","nameEn":"Jiaozuo"},{"id":1024,"name":"马鞍山","nameEn":"Ma'anshan"},{"id":378,"name":"宁德","nameEn":"Ningde"},{"id":884,"name":"英德","nameEn":"Yingde"},{"id":110,"name":"延安","nameEn":"Yan'an"},{"id":3053,"name":"梅州","nameEn":"Meizhou"},{"id":1201,"name":"宁海","nameEn":"Ninghai"},{"id":548,"name":"诸暨","nameEn":"Zhuji"},{"id":181,"name":"安阳","nameEn":"Anyang"},{"id":21939,"name":"南澳","nameEn":"Nanao"},{"id":267,"name":"广元","nameEn":"Guangyuan"},{"id":412,"name":"瑞丽","nameEn":"Ruili"},{"id":4243,"name":"弥勒","nameEn":"Mile"},{"id":1454,"name":"济源","nameEn":"Jiyuan"},{"id":1094,"name":"许昌","nameEn":"Xuchang"},{"id":1472,"name":"宿迁","nameEn":"Suqian"},{"id":1140,"name":"百色","nameEn":"Baise"},{"id":1708,"name":"荔波","nameEn":"Libo"}],
      labaobaoHomeUrl: 'https://frontend.lobaobao97.com/mark'
    }

    // 日志系统
    var Logger = {
        log: function(msg, level) {
            level = level || LOG_LEVEL.INFO;
            var logPanel = Scheduler.UI.logPanel;
            if (!logPanel) return;
            
            // 使用24小时制时间格式
            var now = new Date();
            var time = now.getHours().toString().padStart(2, '0') + ':' + 
                        now.getMinutes().toString().padStart(2, '0') + ':' + 
                        now.getSeconds().toString().padStart(2, '0');
            
            var levelIndicator = level === LOG_LEVEL.ERROR ? '❌' : 
                                level === LOG_LEVEL.WARN ? '⚠️' : '✅';
            logPanel.textContent += '[' + time + '] ' + levelIndicator + ' ' + msg + '\n';
            logPanel.scrollTop = logPanel.scrollHeight;
        },
        
        info: function(msg) { this.log(msg, LOG_LEVEL.INFO); },
        warn: function(msg) { this.log(msg, LOG_LEVEL.WARN); },
        error: function(msg) { this.log(msg, LOG_LEVEL.ERROR); }
    };

    var CryptoUtils = {
        fixKey16: function(key) {
        if (!key) key = '';
        if (key.length > 16) return key.slice(0, 16);

        var filler = [];
        var fillerChar = 'g'.charCodeAt(0);
        for (var i = 0; i < 16 - key.length; i++) {
            filler.push(String.fromCharCode(fillerChar));
            fillerChar += 2;
            if (fillerChar > 'z'.charCodeAt(0)) fillerChar = 'a'.charCodeAt(0);
        }
        return key + filler.join('');
        },

        decrypt: function(base64CipherText, key) {
        // 检查 crypto 支持
        if (!window.crypto || !window.crypto.subtle) {
            return Promise.reject(new Error('Web Crypto API 不可用'));
        }
        
        var binaryStr = atob(base64CipherText);
        var bytes = new Uint8Array(binaryStr.length);
        for (var i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }

        var iv = bytes.slice(0, 16);
        var ciphertext = bytes.slice(16);

        var encoder = new TextEncoder ? new TextEncoder() : { encode: function(str) {
            var utf8 = unescape(encodeURIComponent(str));
            var arr = new Uint8Array(utf8.length);
            for (var i = 0; i < utf8.length; i++) {
            arr[i] = utf8.charCodeAt(i);
            }
            return arr;
        }};
        
        var fixedKey = this.fixKey16(key);
        var keyRaw = encoder.encode(fixedKey);

        return crypto.subtle.importKey(
            'raw',
            keyRaw,
            { name: 'AES-CBC' },
            false,
            ['decrypt']
        ).then(function(cryptoKey) {
            return crypto.subtle.decrypt(
            { name: 'AES-CBC', iv: iv },
            cryptoKey,
            ciphertext
            );
        }).then(function(decryptedBuffer) {
            var decoder = new TextDecoder ? new TextDecoder() : {
            decode: function(buffer) {
                var binary = '';
                var bytes = new Uint8Array(buffer);
                var len = bytes.byteLength;
                for (var i = 0; i < len; i++) {
                binary += String.fromCharCode(bytes[i]);
                }
                return decodeURIComponent(escape(binary));
            }
            };
            return decoder.decode(decryptedBuffer);
        });
        }
    };

    // ----------------------------------------------------
    // 稳定异步任务调度器 (核心重构逻辑)
    // ----------------------------------------------------
    const Scheduler = {
        STATE_KEY: 'lobaobao_plugin_state',
        ACCOUNT_KEY: 'lobaobao_plugin',
        TASK_KEY: 'lobaobao_plugin_task',
        TASK_TRACKED_KEY: 'lobaobao_plugin_tasktracked',
        currentController: null,
        UI: { 
          panel: null, 
          statusDisplay: null, 
          timer: null,  
          dragState: {
            isDragging: false,
            currentX: 0,
            currentY: 0,
            initialX: 0,
            initialY: 0,
            xOffset: 0,
            yOffset: 0
          },
          element: null,
        }, 

        // --- 状态和配置管理 ---
        getDefaultConfig() {
            return {
                // 账号相关
                voucherNo: '', // 当前选中的卡密 (select value)
                voucherNolist: '', // 多个卡密 (textarea value)
                ugroup: '', // 当前选中的用户组 (select value, e.g., '123_组名')
                uname: '', // 当前选中的用户名
                upass: '', // 当前选中的密码
                unamelist: '', // 多个账号 (textarea value)
                speed: 5,        // 自动间隔最小秒数
                speedMax: 15,    // 自动间隔最大秒数
                mcity: 6,        // 最大切换城市数
                mtask: 30,       // 最大做题数
                counttask: 5,    // 每轮做题最小数
                counttaskMax: 10, // 每轮做题最大数
                countspeed: 200, // 每轮休息最小毫秒数
                countspeedMax: 300, // 每轮休息最大毫秒数
                priorityCities: '北京市|上海市|广州市|深圳市|成都市|杭州市|重庆市|武汉市|南京市|西安市|苏州市|天津市|长沙市|郑州市|东莞市|青岛市|合肥市|宁波市|佛山市|南昌市' // 优先顺序城市列表
            };
        },
        /**
         * 获取存储的配置，并检查是否过期。
         * - 不再返回 this.getDefaultConfig()。
         * - 配置无效或过期时返回空对象 {}。
         * - 配置有效时返回存储的 JSON 数据。
         * * @param {string} key - 配置键名。
         * @returns {object} - 未过期或有效的配置对象，否则返回 {}。
         */
        getConfig(key) {
            try {
                const configStr = localStorage.getItem(key);

                if (!configStr) {
                    // 1. 配置不存在，返回空对象
                    return {};
                }

                const storedItem = JSON.parse(configStr);

                // 检查配置是否包含过期时间，并且是否已过期
                if (storedItem && storedItem.expiry && storedItem.expiry < Date.now()) {
                    // 2. 已过期：移除旧缓存，并返回空对象
                    localStorage.removeItem(key);
                    //Logger.warn(`配置 ${key} 已过期，已清除缓存并返回空对象。`);
                    return {};
                }

                // 3. 未过期或永不过期：返回存储的数据
                if (storedItem && storedItem.data) {
                    return storedItem.data;
                }
                
                // 4. 如果存储结构不正确（例如缺少 .data 字段），返回空对象
                return {};

            } catch (e) {
                // 5. 捕获 JSON 解析或读取异常，返回空对象
                Logger.error('读取配置失败，返回空对象。', e);
                return {};
            }
        },

        /**
         * 保存配置到本地存储，并可设置过期时间。
         * @param {string} key - 配置键名。
         * @param {object} data - 待保存的配置数据。
         * @param {number} [expiryHours=0] - 有效期（小时）。不传或传 0 表示永不过期。
         */
        setConfig(key, data, expiryHours) {
            try {
                let expiryTimestamp = null;

                // 如果传入了大于 0 的有效期，则计算过期时间戳
                if (expiryHours && expiryHours > 0) {
                    // Date.now() + 小时数 * 60 分钟 * 60 秒 * 1000 毫秒
                    expiryTimestamp = Date.now() + expiryHours * 60 * 60 * 1000;
                }

                // 存储包含数据和过期时间戳的新对象结构
                const storedData = {
                    data: data,
                    expiry: expiryTimestamp 
                };

                localStorage.setItem(key, JSON.stringify(storedData));

                // 如果是配置变更，触发 UI 同步
                if(key === this.ACCOUNT_KEY) {
                    this.syncConfigToUI(); 
                }
            } catch (e) {
                console.error('保存配置失败:', e);
            }
        },

        getDefaultState() {
            return {
                status: 'STOPPED',
                nextRunTime: 0,
                taskId: null,
            };
        },

        getRunState() {
            try {
                const state = this.getConfig(this.STATE_KEY);
                return Object.assign(this.getDefaultState(), state);
            } catch (e) {
                return this.getDefaultState();
            }
        },

        setRunState(newState) {
            try {
                this.setConfig(this.STATE_KEY, newState);
                this.updateUIStatus(newState); // 状态变更时更新 UI
            } catch (e) {
                console.error('保存状态失败:', e);
            }
        },
        // --- 核心工具函数 ---
        generateUniqueID() {
            const now = new Date();
            //const dd = String(now.getDate()).padStart(2, '0');
            const hh = String(now.getHours()).padStart(2, '0');
            const mm = String(now.getMinutes()).padStart(2, '0');
            const ss = String(now.getSeconds()).padStart(2, '0');
            const sss = String(now.getMilliseconds()).padStart(3, '0');
            
            // 生成3位随机数
            const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
            
            return `${hh}${mm}${ss}${sss}${random}`;
        },
        getRandomDelayMs() {
            const config = this.getConfig(this.ACCOUNT_KEY);
            const taskTracked = this.getConfig(this.TASK_TRACKED_KEY) || {};
            let minMs = parseInt(config.speed) * 1000;
            let maxMs = parseInt(config.speedMax) * 1000;
            const countspeed = parseInt(config.countspeed) * 1000 || 0;
            const countspeedMax = parseInt(config.countspeedMax) * 1000 || 0;

            if (isNaN(minMs) || isNaN(maxMs) || minMs > maxMs) {
                 // 使用默认值确保不崩溃
                 return (this.getDefaultConfig().speed * 1000 + this.getDefaultConfig().speedMax * 1000) / 2;
            }

            if (taskTracked.hid === '') {
                const waittask = taskTracked.waittask || 0;
                const donetask = taskTracked.donetask || 0;
                //如果有任务跟踪数据，调整为任务的延迟总数
                const now = new Date();
                const minutes = now.getMinutes();
                // 检查是否在整点前5分钟内（例如 9:55:00 - 9:59:59）
                if (minutes >= 55) {
                    // 设置最小延迟为6分钟(360000毫秒)，最大延迟为8分钟(480000毫秒)
                    minMs = 5 * 60 * 1000;
                    maxMs = 8 * 60 * 1000;
                    this.taskTracked('', 'waittask', '', null);
                    Logger.info(`已切换为整点休息模式`);
                } else if(donetask >= waittask && waittask !== 0) {
                    minMs = countspeed;
                    maxMs = countspeedMax;
                    this.taskTracked('', 'waittask', '', null);
                    Logger.info(`已切换为任务延迟休息模式`);
                }
            }

            //console.log(`随机延迟时间：${minMs} - ${maxMs}`);
            return Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
        },

        sleep(ms, signal) {
            // ... (sleep 实现与上一步相同)
            return new Promise((resolve, reject) => {
                if (signal.aborted) {
                    return reject(new Error('Task aborted during sleep setup'));
                }
                const timeoutId = setTimeout(() => {
                    signal.removeEventListener('abort', onAbort);
                    resolve();
                }, ms);
                const onAbort = () => {
                    clearTimeout(timeoutId);
                    reject(new Error('Task aborted during sleep'));
                };
                signal.addEventListener('abort', onAbort, { once: true });
            });
        },

        /**
         * 封装的异步 HTTP 请求方法，支持 GET/POST/JSON，并与 AbortController 信号同步。
         * @param {string} url - 请求 URL。
         * @param {object} options - Fetch API options，可选 method, headers, body。
         * @param {AbortSignal} signal - 用于中断请求的信号。
         * @returns {Promise<Response>} - 返回 Fetch Response 对象。
         */
        async makeHttpRequest(url, options = {}, signal) {
            if (typeof window.fetch === 'undefined') {
                throw new Error('Fetch API 不可用，无法执行 HTTP 请求。');
            }
            
            const fetchOptions = {
                ...options,
                signal: signal || undefined
            };
            
            try {
                const response = await fetch(url, fetchOptions);
                
                if (signal && signal.aborted) {
                    throw new Error('Request aborted by scheduler');
                }

                if (!response.ok) {
                    throw new Error(`HTTP 错误: ${response.status} ${response.statusText}`);
                }
                
                return response;
            } catch (error) {
                if (error.name === 'AbortError' || error.message.includes('aborted')) {
                    throw new Error('Task aborted while fetching data');
                }
                throw error;
            }
        },

        /**
         * 将全角字符转换为半角。
         * @param {string} str - 待转换字符串。
         * @returns {string}
         */
        toHalfWidth(str) {
            return str.replace(/[\uFF01-\uFF5E]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xFEE0))
                    .replace(/\u3000/g, ' '); // 处理全角空格
        },

        /**
         * 提取酒店主体名称，去除括号内分店信息和通用词汇。
         * @param {string} str - 酒店全称。
         * @returns {string} - 酒店主体名称。
         */
        extractMainName(str) {
            return str.replace(/[\s]*[\(\（].*?[\)\）]/g, '') // 去掉括号内信息
                    .replace(/酒店|宾馆|公寓|民宿|客栈|饭店/g, '') // 去掉通用词汇
                    .trim();
        },

        /**
         * 标准化字符串：全角转半角，去空格，小写化。
         * @param {string} str - 待处理字符串。
         * @returns {string} - 标准化后的字符串。
         */
        normalize(str) {
            str = this.toHalfWidth(str);
            str = str.replace(/\s+/g, '').toLowerCase();
            return str;
        },

        /**
         * 计算 Jaro-Winkler 相似度（核心匹配算法）。
         * ⚠️ 假设依赖了 this.normalize 方法。
         * @param {string} s1 - 字符串 1。
         * @param {string} s2 - 字符串 2。
         * @returns {number} - 相似度分数 (0.00 to 1.00)。
         */
        jaroWinklerSimilarity(s1, s2) {
            s1 = this.normalize(s1);
            s2 = this.normalize(s2);
            // ... (保持您原有的 Jaro-Winkler 算法实现，它已是正确的同步代码)
            if (s1 === s2) return 1;
            if (!s1 || !s2) return 0;

            const m = Math.max(s1.length, s2.length);
            const matchDistance = Math.floor(m / 2) - 1;
            const s1Matches = Array(s1.length).fill(false);
            const s2Matches = Array(s2.length).fill(false);

            let matches = 0, transpositions = 0;

            for (let i = 0; i < s1.length; i++) {
                const start = Math.max(0, i - matchDistance);
                const end = Math.min(i + matchDistance + 1, s2.length);
                for (let j = start; j < end; j++) {
                    if (!s2Matches[j] && s1[i] === s2[j]) {
                        s1Matches[i] = true;
                        s2Matches[j] = true;
                        matches++;
                        break;
                    }
                }
            }
            if (matches === 0) return 0;

            let k = 0;
            for (let i = 0; i < s1.length; i++) {
                if (!s1Matches[i]) continue;
                while (!s2Matches[k]) k++;
                if (s1[i] !== s2[k]) transpositions++;
                k++;
            }
            transpositions /= 2;

            let jaro = ((matches / s1.length) + (matches / s2.length) + ((matches - transpositions) / matches)) / 3;

            let prefix = 0;
            for (let i = 0; i < Math.min(4, s1.length, s2.length); i++) {
                if (s1[i] === s2[i]) prefix++;
                else break;
            }
            jaro += prefix * 0.1 * (1 - jaro);

            return parseFloat(jaro.toFixed(2));
        },
    
        // --- UI 逻辑 (扩展) ---
        createControlPanel() {
            const panel = document.createElement('div');
            panel.id = 'labaobao-control-panel';
            panel.style.cssText = `
                position: fixed; right: 30px; top: 40px; width: 340px; max-height: 640px;
                overflow-y: auto; background: white; border: 1px solid #ccc;
                z-index: 999999; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.12);
            `;

            // HTML 模板包含所有新元素
            panel.innerHTML = `
                <div id="panel-drag-header" style="padding:8px 12px; background:#f9f9f9; border-bottom:1px solid #eaeaea; cursor:move; border-radius:4px 4px 0 0;">
                  <span style="font-weight:bold;">劳保保助手v1.7.1</span>
                  &nbsp;<a href="https://my.ctrip.com/myinfo/all" target="_blank">个人中心</a>
                  <span style="float:right; cursor:pointer;" id="panel-toggle-btn">︿</span>
                </div>
                <div id="panel-content">
                  <div class="panel-row tiny" style="background:#f9f9f9; border-bottom:1px solid #eaeaea;">
                    可用积分: <span id="availScore">-</span> | 已切城市: <span id="donecity">-</span> | 已做题目: <span id="donetask">-</span>
                    <button id="resetBtn" style="padding:4px 8px; font-size:8px; background:#ff4d4f; color:#fff; border:none; border-radius:4px; cursor:pointer;">重置</button>
                  </div>
                  <div class="panel-row toggle" style="display:flex; align-items:center; justify-content:space-between;">
                    <div id="setting-tags" style="display:flex; gap:6px;">
                      <button id="manageBtn" class="tag-btn" type="button">账号设置</button>
                    </div>
                  </div>
                  <div class="panel-row toggle">
                    <select id="ugroup" style="display:none;" ></select>
                    <select id="voucherNo"></select>
                    <textarea id="voucherNolist" placeholder="卡1\n卡2" style="display:none;"></textarea>
                    <select id="uname"></select>
                    <textarea id="unamelist" placeholder="用户名1,密码1\n用户名2,密码2" style="display:none;"></textarea>
                  </div>
                  <div class="panel-row toggle" >
                    <div style="display:table; width:100%; table-layout:fixed;">
                      <div style="display:table-cell; padding-right:10px;">
                        <div style="font-size:12px; color:#666; margin-bottom:6px;">自动间隔(秒)</div>
                        <div style="display:flex; gap:4px; align-items:center;">
                          <input id="speed" value="25" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                          <span style="font-size:12px; color:#666;">~</span>
                          <input id="speedMax" value="45" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                        </div>
                      </div>
                      <div style="display:table-cell; padding:0 10px;">
                        <div style="font-size:12px; color:#666; margin-bottom:6px;">最大城市</div>
                        <input id="mcity" value="2" />
                      </div>
                      <div style="display:table-cell; padding-left:10px;">
                        <div style="font-size:12px; color:#666; margin-bottom:6px;">最大题数</div>
                        <input id="mtask" value="8" />
                      </div>
                    </div>
                  </div>
                  <div class="panel-row toggle">
                    <div style="display:table; width:100%; table-layout:fixed;">
                        <div style="display:table-cell; padding-right:10px;">
                            <div style="font-size:12px; color:#666; margin-bottom:6px;">每做题目数</div>
                            <div style="display:flex; gap:4px; align-items:center;">
                                <input id="counttask" value="3" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                                <span style="font-size:12px; color:#666;">~</span>
                                <input id="counttaskMax" value="5" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                            </div>
                        </div>
                        <div style="display:table-cell; padding:0 10px;">
                            <div style="font-size:12px; color:#666; margin-bottom:6px;">休息间隔(秒)</div>
                            <div style="display:flex; gap:4px; align-items:center;">
                                <input id="countspeed" value="200" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                                <span style="font-size:12px; color:#666;">~</span>
                                <input id="countspeedMax" value="300" style="flex:1; padding:6px; border:1px solid #e6e6e6; border-radius:4px;" />
                            </div>
                        </div>
                    </div>
                  </div>
                  <div class="panel-row toggle">
                    <div style="font-size:12px; color:#666; margin-bottom:6px;">优先顺序切换城市</div>
                    <input id="priorityCities" placeholder="用|分隔，如: 深圳市|广州市" value="北京市|上海市|广州市|深圳市|成都市|杭州市|重庆市|武汉市|南京市|西安市|苏州市|天津市|长沙市|郑州市|东莞市|青岛市|合肥市|宁波市|佛山市|南昌市" style="width:100%; margin-bottom:10px; padding:4px;"/>
                  </div>
                  <div class="panel-row">
                    <button id="startBtn" style="width:100%; padding:8px; border-radius:6px; background:#1677ff; color:#fff; border:none; cursor:pointer;">开始运行</button>
                  </div>
                  <div id="countdownDisplay" class="panel-row" style="background:#f9f9f9; border-bottom:1px solid #eaeaea; height:22px; margin:0 6px;">
                  </div>
                  <div class="panel-row" style="padding-top:4px; padding-bottom:12px;">
                    <div id="logPanel" style="max-height:140px; overflow-y:auto; background:#fafafa; border:1px solid #eee; padding:8px; font-size:12px; white-space:pre-wrap;"></div>
                  </div>
                </div>
            `;
            
            // 样式优化
            const style = document.createElement('style');
            style.textContent = `
              #labaobao-control-panel, #labaobao-control-panel * { box-sizing: border-box; }
              #labaobao-control-panel::-webkit-scrollbar { display: none; }
              #labaobao-control-panel { scrollbar-width: none; -ms-overflow-style: none; }
              #labaobao-control-panel input, #labaobao-control-panel select, #labaobao-control-panel textarea {
                width: 100%; padding: 6px; margin: 0 0 6px 0; border: 1px solid #e6e6e6; border-radius: 4px; background: #fff; font-size:13px;
              }
              #labaobao-control-panel textarea { min-height:72px; resize: vertical; }
              #labaobao-control-panel button { font-family: inherit; }
              #labaobao-control-panel .tag-btn { padding:4px 10px; font-size:12px; border-radius:12px; border:1px solid #d9d9d9; background:#fafafa; cursor:pointer; color:#333; height:30px; line-height:18px; }
              #labaobao-control-panel .tag-btn:hover { background:#f0f0f0; }
              #labaobao-control-panel .tag-btn.active { background:#1890ff; color:#fff; border-color:#1890ff; }
              #labaobao-control-panel #panel-content { padding: 0; }
              #labaobao-control-panel .panel-row { padding: 4px 6px; }
              #labaobao-control-panel .panel-row.tiny { padding: 3px 6px; }
              #labaobao-control-panel h4 { margin: 0; padding: 0; font-size:15px; }
              #labaobao-control-panel a { color: #000; text-decoration: none; font-size: 11px; }
              #labaobao-control-panel a:hover { text-decoration: underline; }
              #labaobao-control-panel #resetBtn { float: right; margin-left: 8px; }
              #labaobao-control-panel input[type="number"], #labaobao-control-panel input[type="text"] {
                width: 100%; padding: 6px; margin: 0 0 6px 0; border: 1px solid #e6e6e6; border-radius: 4px; background: #fff; font-size:13px;
              }
              #labaobao-control-panel .input-group {
                display: flex; align-items: center; gap: 4px;
              }
              #labaobao-control-panel .input-group input {
                flex: 1; margin-bottom: 0;
              }
              #labaobao-control-panel .input-group span {
                font-size: 12px; color: #666;
              }
            `;
            document.head.appendChild(style);


            document.body.appendChild(panel);
            this.bindUIElements();
            this.bindConfigEvents();
        },
        
        bindUIElements() {
            this.UI.panel = document.getElementById('labaobao-control-panel');
            this.UI.dragHeader = document.getElementById('panel-drag-header');
            this.UI.togglePanel = document.getElementById('panel-toggle-btn');
            this.UI.availScore = document.getElementById('availScore');
            this.UI.donecity = document.getElementById('donecity');
            this.UI.donetask = document.getElementById('donetask');
            this.UI.countdown = document.getElementById('countdown');
            this.UI.resetBtn = document.getElementById('resetBtn');
            this.UI.manageBtn = document.getElementById('manageBtn');
            this.UI.ugroup = document.getElementById('ugroup');
            this.UI.voucherNo = document.getElementById('voucherNo');
            this.UI.voucherNolist = document.getElementById('voucherNolist');
            this.UI.uname = document.getElementById('uname');
            this.UI.unamelist = document.getElementById('unamelist');
            this.UI.speed = document.getElementById('speed');
            this.UI.speedMax = document.getElementById('speedMax');
            this.UI.mcity = document.getElementById('mcity');
            this.UI.mtask = document.getElementById('mtask');
            this.UI.counttask = document.getElementById('counttask');
            this.UI.counttaskMax = document.getElementById('counttaskMax');
            this.UI.countspeed = document.getElementById('countspeed');
            this.UI.countspeedMax = document.getElementById('countspeedMax');
            this.UI.priorityCities = document.getElementById('priorityCities');
            this.UI.countdownDisplay = document.getElementById('countdownDisplay');
            this.UI.startBtn = document.getElementById('startBtn');
            this.UI.logPanel = document.getElementById('logPanel');

            this.UI.startBtn.addEventListener('click', () => this.startTask());
            this.UI.togglePanel.addEventListener('click', () => this.togglePanel());
            this.UI.resetBtn.addEventListener('click', () => this.resetTaskState());
            this.UI.manageBtn.addEventListener('click', () => this.manageConfig());
            this.UI.ugroup.addEventListener('change', () => this.changeConfig());

            // 拖动
            this.UI.dragHeader.addEventListener('mousedown', this.dragStart.bind(this));
            document.addEventListener('mouseup', this.dragEnd.bind(this));
            document.addEventListener('mousemove', this.drag.bind(this));
        },

        dragStart: function(e) {
          var togglePanel = this.UI.togglePanel;
          if (e.target === togglePanel) return;
          
          this.UI.dragState.initialX = e.clientX - this.UI.dragState.xOffset;
          this.UI.dragState.initialY = e.clientY - this.UI.dragState.yOffset;
          
          if (e.target.id === 'panel-drag-header') {
            this.UI.dragState.isDragging = true;
          }
        },
        
        dragEnd: function() {
          this.UI.dragState.initialX = this.UI.dragState.currentX;
          this.UI.dragState.initialY = this.UI.dragState.currentY;
          this.UI.dragState.isDragging = false;
        },
        
        drag: function(e) {
          if (this.UI.dragState.isDragging) {
            e.preventDefault();
            this.UI.dragState.currentX = e.clientX - this.UI.dragState.initialX;
            this.UI.dragState.currentY = e.clientY - this.UI.dragState.initialY;
            
            this.UI.dragState.xOffset = this.UI.dragState.currentX;
            this.UI.dragState.yOffset = this.UI.dragState.currentY;
            
            var panel = this.UI.panel;
            var transformValue = 'translate3d(' + this.UI.dragState.currentX + 'px, ' + this.UI.dragState.currentY + 'px, 0)';

            if (panel.style.webkitTransform !== undefined) {
              panel.style.webkitTransform = transformValue;
            } else {
              panel.style.transform = transformValue;
            }
          }
        },

        togglePanel (e) {
            var panelContent = this.UI.panel;
            var config = this.getConfig(this.ACCOUNT_KEY);
            var togglePanel = e !== undefined && e === 0 ? config.panelCollapsed : !config.panelCollapsed || false;

            if (togglePanel) {
                // 折叠时，只隐藏中间的 panel-row（保留第一行积分显示、按钮行和最后一行日志区域）
                var panelRows = panelContent.querySelectorAll('.panel-row.toggle');
                for (var i = 0; i < panelRows.length; i++) {
                    panelRows[i].style.display = 'none';
                }
                this.UI.togglePanel.textContent = '﹀';
                togglePanel = true;
            } else {
                //panel.style.maxHeight = originalPanelHeight;
                //contentDiv.style.display = 'block';
                // 展开时，显示所有 panel-row
                var panelRows = panelContent.querySelectorAll('.panel-row.toggle');
                for (var i = 0; i < panelRows.length; i++) {
                    panelRows[i].style.display = 'block';
                }
                this.UI.togglePanel.textContent = '︿';
                togglePanel = false;
            }

            if(togglePanel != config.panelCollapsed && !e && e !== 0) {
                //console.log('togglePanel', togglePanel);
                config.panelCollapsed = togglePanel;
                this.setConfig(this.ACCOUNT_KEY, config);
            }
        },
        
        bindConfigEvents() {
            // 加载配置并同步到 UI
            this.togglePanel(0);
            this.syncConfigToUI();
        },

        syncConfigToUI() {
            const config = this.getConfig(this.ACCOUNT_KEY);
            //console.log('syncConfigToUI', JSON.stringify(config));
            var voucherNoField = document.getElementById('voucherNo');
            var ugroupField = document.getElementById('ugroup');
            var unameField = document.getElementById('uname');
            var mcityField = document.getElementById('mcity');
            var mtaskField = document.getElementById('mtask');
            var speedField = document.getElementById('speed');
            var speedMaxField = document.getElementById('speedMax');
            var counttaskField = document.getElementById('counttask');
            var counttaskMaxField = document.getElementById('counttaskMax');
            var countspeedField = document.getElementById('countspeed');
            var countspeedMaxField = document.getElementById('countspeedMax');
            var priorityCitiesField = document.getElementById('priorityCities');
            
            // ---- voucherNo 下拉框 ----
            if (voucherNoField) {
                voucherNoField.innerHTML = '';
                var voucherNolist = config.voucherNolist || '';
                if (!voucherNolist && config.voucherNo) {
                    voucherNolist = config.voucherNo;
                }
                var lines = voucherNolist.split('\n').filter(line => line.trim() !== '');
                if (lines.length === 0) {
                    var defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = '请添加卡密';
                    voucherNoField.appendChild(defaultOption);
                } else {
                    for (var i = 0; i < lines.length; i++) {
                        var vno = lines[i].trim();
                        var opt = document.createElement('option');
                        opt.value = vno;
                        opt.textContent = (i+1) + ' | ' + (vno.length > 2 ? vno.slice(0, -2) + '**' : vno);
                        voucherNoField.appendChild(opt);
                    }
                }
                if (lines.length > 0) {
                    let targetValue = config.voucherNo || null;
                    let found = -1;
                    if (targetValue) {
                    for (var i = 0; i < voucherNoField.options.length; i++) {
                        if (voucherNoField.options[i].value === targetValue) {
                        found = i; break;
                        }
                    }
                    }
                    if (found !== -1) {
                    voucherNoField.selectedIndex = found;
                    voucherNoField.value = targetValue;
                    voucherNoField.options[found].selected = true;
                    } else {
                    voucherNoField.selectedIndex = 0;
                    voucherNoField.value = voucherNoField.options[0].value;
                    voucherNoField.options[0].selected = true;
                    }
                }
            }

            if (ugroupField && config.ugroup) {
                ugroupField.innerHTML = '';
                var ugrouplist = config.ugrouplist || '';
                var lines = ugrouplist.split('\n').filter(line => line.trim() !== '');
                if (lines.length > 0) {
                    for (var i = 0; i < lines.length; i++) {
                    var ug = lines[i].split('_');

                    if(ug.length === 2) {
                        var opt = document.createElement('option');
                        opt.value = lines[i].trim();
                        opt.textContent = (i+1) + ' | ' + ug[1];
                        ugroupField.appendChild(opt);
                    }
                    }
                }

                if (lines.length > 0) {
                    let targetValue = config.ugroup || null;
                    let found = -1;
                    if (targetValue) {
                    for (var i = 0; i < ugroupField.options.length; i++) {
                        if (ugroupField.options[i].value === targetValue) {
                        found = i; break;
                        }
                    }
                    }
                    if (found !== -1) {
                        ugroupField.selectedIndex = found;
                        ugroupField.value = targetValue;
                        ugroupField.options[found].selected = true;
                    } else {
                        if(ugroupField.options.length > 0) {
                            ugroupField.selectedIndex = 0;
                            ugroupField.value = ugroupField.options[0].value;
                            ugroupField.options[0].selected = true;
                        }
                    }
                }
            }

            // ---- uname 下拉框 ----
            if (unameField) {
                unameField.innerHTML = '';
                var unamelist = config.unamelist || '';
                if (!unamelist && config.uname && config.upass) {
                    unamelist = config.uname + ',' + config.upass;
                }
                var lines = unamelist.split('\n').filter(line => line.trim() !== '');
                if (lines.length === 0) {
                    var defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = '请添加题目账号';
                    unameField.appendChild(defaultOption);
                } else {
                    for (var i = 0; i < lines.length; i++) {
                        var parts = lines[i].replace('，', ',').split(',');
                        if (parts.length >= 2) {
                            var uname = parts[0].trim();
                            var upass = parts.slice(1).join(',').trim();
                            var opt = document.createElement('option');
                            opt.value = uname + ',' + upass;
                            opt.textContent = (i+1) + ' | ' + uname;
                            unameField.appendChild(opt);
                        }
                    }
                }
                if (lines.length > 0) {
                    let targetValue = config.uname && config.upass ? (config.uname + ',' + config.upass) : null;
                    let found = -1;
                    if (targetValue) {
                    for (var i = 0; i < unameField.options.length; i++) {
                        if (unameField.options[i].value === targetValue) {
                        found = i; break;
                        }
                    }
                    }
                    if (found !== -1) {
                    unameField.selectedIndex = found;
                    unameField.value = targetValue;
                    unameField.options[found].selected = true;
                    } else {
                    unameField.selectedIndex = 0;
                    unameField.value = unameField.options[0].value;
                    unameField.options[0].selected = true;
                    }
                }
            }

            // ---- 其它字段 ----
            if (mcityField && config.mcity) {
                if (config.mcity) mcityField.value = config.mcity; 
            }
            if (mtaskField && config.mtask) {
                if (config.mtask) mtaskField.value = config.mtask; 
            }
            if (speedField && config.speed) {
                if (config.speed) speedField.value = config.speed; 
            }
            if( speedMaxField && config.speedMax) {
                if (config.speedMax) speedMaxField.value = config.speedMax;
            }
            if (counttaskField && config.counttask) {
                if (config.counttask) counttaskField.value = config.counttask;
            }
            if (counttaskMaxField && config.counttaskMax) {
                if (config.counttaskMax) counttaskMaxField.value = config.counttaskMax;
            }
            if (countspeedField && config.countspeed) {
                if (config.countspeed) countspeedField.value = config.countspeed;
            }
            if (countspeedMaxField && config.countspeedMax) {
                if (config.countspeedMax) countspeedMaxField.value = config.countspeedMax;
            }
            if (priorityCitiesField && config.priorityCities) {
                priorityCitiesField.value = config.priorityCities;
            }

            if (config.panelx !== undefined && config.panely !== undefined) {
                this.UI.dragState.currentX = config.panelx;
                this.UI.dragState.currentY = config.panely;
                this.UI.dragState.xOffset = config.panelx;
                this.UI.dragState.yOffset = config.panely;
                
                // 应用位置变换
                const transformValue = `translate3d(${config.panelx}px, ${config.panely}px, 0)`;
                if (this.UI.panel.style.webkitTransform !== undefined) {
                    this.UI.panel.style.webkitTransform = transformValue;
                } else {
                    this.UI.panel.style.transform = transformValue;
                }
            }

            var tracked = this.getConfig(this.TASK_TRACKED_KEY);
            this.updateDonetaskAndDonecity(tracked.donetask || 0, tracked.donecity || 0);
        },

        async saveConfigFromUI() {
            var voucherNo = this.UI.voucherNo.value.trim();
            var unamelist = this.UI.unamelist.value.trim();
            var uname = this.UI.uname.value.trim();
            var speed = this.UI.speed.value.trim();
            var speedMax = this.UI.speedMax.value.trim();
            var mcity = this.UI.mcity.value.trim();
            var mtask = this.UI.mtask.value.trim();
            var counttask = this.UI.counttask.value.trim();
            var counttaskMax = this.UI.counttaskMax.value.trim();
            var countspeed = this.UI.countspeed.value.trim();
            var countspeedMax = this.UI.countspeedMax.value.trim();
            var priorityCities = this.UI.priorityCities.value.trim();

            // 如果只有一行数据 并且没有逗号判断，注意逗号需要处理全角问题
            if (unamelist && unamelist.split('\n').filter(line => line.trim() !== '').length === 1 && 
                !unamelist.replace('，', ',').includes(',') && this.UI.unamelist.style.display === 'block') {
                await this.loadApiSettings(unamelist); 
                Logger.info('已加载配置完成');
                return false;
            } else if (!voucherNo || !uname || !mtask || !speed || !speedMax) {
                Logger.error('请配置完整信息再点击运行');
                return false;
            }

            // 验证数字输入
            if (isNaN(mcity) || parseInt(mcity, 10) <= 0  || isNaN(mtask) || parseInt(mtask, 10) <= 0  || isNaN(speed) || parseInt(speed, 10) <= 0  || isNaN(speedMax) || parseInt(speedMax, 10) <= 0 
                || isNaN(counttask) || parseInt(counttask, 10) <= 0 || isNaN(counttaskMax) || parseInt(counttaskMax, 10) <= 0 || isNaN(countspeed) || parseInt(countspeed, 10) <= 0 || isNaN(countspeedMax) || parseInt(countspeedMax, 10) <= 0) {
                Logger.error('巡检间隔和切换城市数和任务数必须为数字');
                return false;
            }

            var priorityCitiesList = [];
            if (priorityCities) {
                // 处理全角和半角字符，统一转换为半角并去除空格
                priorityCitiesList = priorityCities
                .split('|')
                .map(city => city.trim().replace(/[\uFF01-\uFF5E]/g, (match) => 
                    String.fromCharCode(match.charCodeAt(0) - 0xFEE0)))
                .filter(city => city.length > 0);
            }

            if(priorityCitiesList.length > 0 && mcity > priorityCitiesList.length) {
                mcity = priorityCitiesList.length;
            }

            // 验证巡检间隔
            if (parseInt(speed, 10) < 2) {
                Logger.error('巡检间隔不能小于2秒');
                return false;
            }

            if (parseInt(speed, 10) > parseInt(speedMax, 10)) {
                Logger.error('最小巡检间隔不能大于最大巡检间隔');
                return false;
            }

            //分解账号与密码
            var unameupass = uname.split(',');
            if(unameupass.length != 2) {
                Logger.error('请输入正确的账号与密码');
                return;
            }

            //判断是否保存配置
            if(this.UI.manageBtn.classList.contains('active')) {
                Logger.error('请先点击账号保存按钮');
                return false;
            }

            var config = this.getConfig(this.ACCOUNT_KEY);
            config.voucherNo = voucherNo;
            config.uname = unameupass[0].trim();
            config.upass = unameupass[1].trim();
            config.speed = parseInt(speed, 10);
            config.speedMax = parseInt(speedMax, 10);
            config.mcity = parseInt(mcity, 10);
            config.mtask = parseInt(mtask, 10);
            config.counttask = parseInt(counttask, 10);
            config.counttaskMax = parseInt(counttaskMax, 10);
            config.countspeed = parseInt(countspeed, 10);
            config.countspeedMax = parseInt(countspeedMax, 10);
            config.priorityCitiesList = priorityCitiesList;
            config.panelx = this.UI.dragState.currentX;
            config.panely = this.UI.dragState.currentY;

            /*
            var config = {
                voucherNo: voucherNo,
                uname: unameupass[0].trim(),
                upass: unameupass[1].trim(),
                speed: parseInt(speed, 10),
                speedMax: parseInt(speedMax, 10),
                mcity: parseInt(mcity, 10),
                mtask: parseInt(mtask, 10),
                counttask: parseInt(counttask, 10),
                counttaskMax: parseInt(counttaskMax, 10),
                countspeed: parseInt(countspeed, 10),
                countspeedMax: parseInt(countspeedMax, 10),
                priorityCitiesList: priorityCitiesList,
            }*/

            this.setConfig(this.ACCOUNT_KEY, config);

            return true;
        },

        updateUIStatus(state) {
            // 清除旧的计时器
            if (this.UI.timer) clearInterval(this.UI.timer);

            // 1. 更新运行时指标
            //this.UI.pointsVal.textContent = state.points;
            //this.UI.citiesVal.textContent = state.citiesSwitched;
            //this.UI.questionsVal.textContent = state.questionsDone;

            if (state.status === 'RUNNING') {
                this.UI.startBtn.textContent = '停止运行';
                this.UI.startBtn.style.backgroundColor = '#ff4d4f';
                this.UI.startBtn.style.color = 'white';
                
                // 2. 倒计时执行时间
                const updateCountdown = () => {
                    const now = Date.now();
                    
                    if (state.nextRunTime === 0) {
                        this.UI.countdownDisplay.textContent = '正在执行任务...';
                    } else if (state.nextRunTime > now) {
                        const remainingSeconds = Math.ceil((state.nextRunTime - now) / 1000);
                        this.UI.countdownDisplay.textContent = `倒计时执行: ${remainingSeconds} 秒`;
                    } else {
                        // 倒计时结束，任务应该已经开始或即将开始
                        this.UI.countdownDisplay.textContent = '准备执行下一轮...';
                        clearInterval(this.UI.timer);
                    }
                    
                    if (this.getRunState().status !== 'RUNNING') {
                        clearInterval(this.UI.timer);
                        this.UI.countdownDisplay.textContent = '';
                    }
                };

                this.UI.timer = setInterval(updateCountdown, 1000);
                updateCountdown(); // 立即执行一次
                
            } else {
                this.UI.startBtn.textContent = '开始运行';
                this.UI.startBtn.style.backgroundColor = '';
                this.UI.startBtn.style.color = '';
                this.UI.countdownDisplay.textContent = '';
            }
        },
        resetTaskState () {
            // 重置任务数据
            this.taskTracked('', 'reset', '', null);
            Logger.info('任务数据已重置');
        },
        updateScores(avail) {
            var availSpan = document.getElementById('availScore');
            if (availSpan) availSpan.textContent = avail;
        },
        updateDonetaskAndDonecity(donetask, donecity) {
            var donetaskSpan = document.getElementById('donetask');
            if (donetaskSpan) donetaskSpan.textContent = donetask;

            var donecitySpan = document.getElementById('donecity');
            if (donecitySpan) donecitySpan.textContent = donecity;

        },
        manageConfig() {
            var voucherNo = this.UI.voucherNo;
            var voucherNolist = this.UI.voucherNolist;
            var ugroup = this.UI.ugroup;
            var uname = this.UI.uname;
            var unamelist = this.UI.unamelist;
            var manageBtn = this.UI.manageBtn;
            var mcity = this.UI.mcity.value.trim();
            var mtask = this.UI.mtask.value.trim();
            var speed = this.UI.speed.value.trim();
            var speedMax = this.UI.speedMax.value.trim();
            var counttask = this.UI.counttask.value.trim();
            var counttaskMax = this.UI.counttaskMax.value.trim();
            var countspeed = this.UI.countspeed.value.trim();
            var countspeedMax = this.UI.countspeedMax.value.trim();
            var priorityCities = this.UI.priorityCities.value.trim();

            // 切换到编辑模式：显示 textarea，隐藏 select；按钮变为 "账号保存" 并高亮
            if (!voucherNo || !voucherNolist || !uname || !unamelist) return;

            // 保存并切回选择模式
            var config = this.getConfig(this.ACCOUNT_KEY) || {};

            if (voucherNo.style.display === '' || voucherNolist.style.display === 'none' 
                || uname.style.display === '' || unamelist.style.display === 'none') {
                voucherNo.style.display = 'none';
                uname.style.display = 'none';
                voucherNolist.style.display = 'block';
                unamelist.style.display = 'block';

                if(ugroup.options.length > 0) {
                    ugroup.style.display = 'block';
                } else {
                    ugroup.style.display = 'none';
                }

                manageBtn.classList.add('active');
                manageBtn.textContent = '账号保存';

                // 加载已保存的用户到编辑框
                voucherNolist.value = config.voucherNolist || '';
                unamelist.value = config.unamelist || '';

                //兼容老账号数据
                if(!voucherNolist.value && config.voucherNo) {
                    voucherNolist.value = config.voucherNo;
                }
                if(!unamelist.value && config.uname && config.upass) {
                    unamelist.value = config.uname + ',' + config.upass;
                }
            } else {
                config.voucherNolist = voucherNolist.value;
                config.ugroup = ugroup.value;
                config.ugrouplist = Array.from(ugroup.options).map(opt => opt.value).join('\n');
                config.unamelist = unamelist.value;
                config.mcity = mcity;
                config.mtask = mtask;
                config.speed = speed;
                config.speedMax = speedMax;
                config.counttask = counttask;
                config.counttaskMax = counttaskMax;
                config.countspeed = countspeed;
                config.countspeedMax = countspeedMax;
                config.priorityCities = priorityCities;

                this.setConfig(this.ACCOUNT_KEY, config);

                ugroup.style.display = 'none';
                voucherNo.style.display = 'block';
                voucherNolist.style.display = 'none';
                uname.style.display = 'block';
                unamelist.style.display = 'none';

                manageBtn.classList.remove('active');
                manageBtn.textContent = '账号设置';

                Logger.info('保存信息成功');
            }
        },
        async changeConfig() {
            var ugroup = this.UI.ugroup.value;
            var ugroupValue = ugroup.split('_'); // [uid, 组名]
            
            if (!ugroupValue[0]) {
                 Logger.warn('用户组切换失败: UID信息不完整。');
                 return;
            }
            // 确保同步 UI 状态
            const currentConfig = this.getConfig(this.ACCOUNT_KEY);
            currentConfig.ugroup = ugroup;
            this.setConfig(this.ACCOUNT_KEY, currentConfig); 
            
            await this.loadApiSettings(ugroupValue[0], ugroupValue[1]); 
        },

        async loadApiSettings(uid, ugroup) {
            const configFields = [
                'voucherNolist', 'ugroup', 'unamelist', 'mcity', 'mtask', 'speed', 'speedMax', 
                'counttask', 'counttaskMax', 'countspeed', 'countspeedMax', 'priorityCities'
            ];
            
            if (!uid) {
                Logger.warn('UID为空，跳过远程配置加载。');
                return;
            }
            
            const url = 'https://www.jpzz.top/api/lobaobao/config?id=' + uid;
            
            try {
                const resp = await this.makeHttpRequest(url, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'omit'
                }, this.currentController ? this.currentController.signal : null);
                
                const result = await resp.json();
                
                if (result.code === 1 && result.data) {
                    var data = result.data;
                    var ugrouplist = [];
                    var dataObj = null;
                    ugroup = ugroup || ''; 

                    if (Array.isArray(data)) {
                        ugrouplist = data.map(item => item.ugroup).filter(g => g); // 过滤空组名
                        for (var i = 0; i < data.length; i++) {
                            if (data[i].ugroup === ugroup || ugroup === '') {
                                dataObj = data[i];
                                ugroup = data[i].ugroup; // 确定实际选择的组名
                                break;
                            }
                        }
                        
                        if (ugrouplist.length > 0) {
                            this.UI.ugroup.innerHTML = '';
                            ugrouplist.forEach((ug, i) => {
                                var opt = document.createElement('option');
                                opt.value = uid + '_' + ug;
                                opt.textContent = (i + 1) + ' | ' + ug;
                                this.UI.ugroup.appendChild(opt);
                            });

                            var targetValue = uid + '_' + (ugroup || '');

                            setTimeout(() => {
                                let found = false;
                                for (let i = 0; i < this.UI.ugroup.options.length; i++) {
                                    if (this.UI.ugroup.options[i].value === targetValue) {
                                        this.UI.ugroup.selectedIndex = i;
                                        this.UI.ugroup.options[i].selected = true;
                                        found = true;
                                        break;
                                    }
                                }
                                
                                // 如果没找到匹配项，默认选择第一项
                                if (!found && this.UI.ugroup.options.length > 0) {
                                    this.UI.ugroup.selectedIndex = 0;
                                    this.UI.ugroup.options[0].selected = true;
                                }
                            }, 0);

                            this.UI.ugroup.style.display = 'block';
                        } else {
                            this.UI.ugroup.style.display = 'none';
                        }

                    } else {
                        dataObj = data;
                        this.UI.ugroup.style.display = 'none';
                    }

                    if (!dataObj) {
                        Logger.warn('未找到匹配的用户组配置。');
                        return;
                    }

                    // 3. 更新 UI 编辑框和本地配置对象
                    const currentConfig = this.getConfig(this.ACCOUNT_KEY);
                    const newConfig = { ...currentConfig, ugrouplist: Array.from(this.UI.ugroup.options).map(opt => opt.value).join('\n') };
                    
                    configFields.forEach(key => {
                        if (dataObj[key] !== undefined) {
                            let value = dataObj[key];
                            // 数组转字符串
                            if ((key === 'voucherNolist' || key === 'unamelist') && Array.isArray(value)) {
                                value = value.join('\n');
                            }
                            
                            // 更新 UI 字段
                            const uiField = this.UI[key];
                            if (uiField) { uiField.value = value; }
                            
                            // 更新配置对象
                            newConfig[key] = value;
                        }
                    });

                    newConfig.ugroup = ugroup;
                    this.setConfig(this.ACCOUNT_KEY, newConfig); 
                } else {
                    throw new Error(`API返回错误: ${result.msg || '未知错误'}`);
                }
            } catch (error) {
                Logger.error('远程加载配置失败: ' + error.message);
                // throw error; // 不再向上抛出，避免阻塞 UI
            }
        },
        /**
         * 通过文本查找并点击按钮，并在点击后等待，支持任务中断。
         * @param {string} text - 按钮文本内容 (模糊匹配)。
         * @param {string} [logSuccess] - 成功点击后的日志信息。
         * @param {string} [logFail] - 未找到或点击失败后的日志信息。
         * @param {number} [delay=1000] - 点击后等待的毫秒数。
         * @param {AbortSignal} signal - 任务中断信号。
         * @returns {Promise<boolean>} - 是否成功点击。
         */
        async findPageButtonByText(text, logSuccess, logFail, delay = 1000, signal) {
            var buttons = document.querySelectorAll('button span');
            var btn = null;
            
            // 查找按钮
            for (var i = 0; i < buttons.length; i++) {
                // 使用更健壮的方式获取按钮元素 (可能按钮文本在 span 外层)
                if (buttons[i].textContent.replace(/\s+/g, '').includes(text)) {
                    // 找到 span 元素的父级 button 或其父级
                    btn = buttons[i].closest('button') || buttons[i].parentNode; 
                    break;
                }
            }
            
            if (btn) {
                btn.click();
                
                if (logSuccess) Logger.info(logSuccess);

                // 记录废弃操作 (保持原有逻辑的日志替换)
                if(logSuccess && logSuccess.indexOf('废弃') !== -1) {
                    await this.taskTracked('', 'cancel', '', signal)
                    //Logger.info('[Tracker] 已记录一次废弃操作。');
                }

                // 【关键重构】使用 await this.sleep(delay, signal) 替换 Promise 链
                await this.sleep(delay, signal); 
                return true;
            } else {
                if (logFail) Logger.error(logFail);
                return false; 
            }
        },
        /**
         * 点击弹窗遮罩层关闭弹窗 (采用坐标点击模拟，更可靠)。
         * 优化点：
         * 1. 升级为 async/await 结构。
         * 2. 增加日志输出，明确操作结果。
         * 3. 兼容之前的 clickButtonByText 方法，作为未找到遮罩时的备选关闭方案。
         * * @param {AbortSignal} [signal] - 任务中断信号，可选，用于点击后的短暂等待。
         * @returns {Promise<boolean>} - 是否成功点击或关闭弹窗。
         */
        async findPageClickPopupMask(signal) {
            const hiddenPanel = document.querySelector('.adm-mask');
            if (hiddenPanel) {
                try {
                    // 检查元素是否存在且不是 display: none（虽然更推荐使用 computed style，但保留用户对 style.display 的关注）
                    if (hiddenPanel.style.display === 'none') {
                        //Logger.warn('弹窗忽略.');
                        return false;
                    }

                    // 获取元素的边界矩形
                    const rect = hiddenPanel.getBoundingClientRect();
                    
                    // 确保元素有大小，否则点击可能无效
                    if (rect.width === 0 && rect.height === 0) {
                        //Logger.warn('弹窗不可见。尝试继续。');
                    }

                    // 创建一个点击事件，使用边界内的坐标 (左上角 10, 10 处) 模拟真实用户点击
                    const clickEvent = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: rect.left + 10,
                        clientY: rect.top + 10
                    });
                    
                    hiddenPanel.dispatchEvent(clickEvent);
                    //Logger.info('关闭弹窗');
                    
                    // 点击后短暂等待 200ms，确保弹窗有时间关闭
                    if (this.sleep && signal) {
                        await this.sleep(200, signal);
                    }
                    return true;
                    
                } catch (error) {
                    //Logger.error('关闭城市下拉框失败: ' + error.message);
                    // 即使失败也尝试后备方案
                }
            }

            // 如果以上操作都失败
            return false;
        },

        /**
         * 【重构】关闭所有基于 .adm-center-popup-wrap 结构的弹窗。
         * 通过点击“取消”或“确定”按钮实现，并在每次点击后短暂等待，确保弹窗正常关闭。
         *
         * @param {string} [buttonText='取消'] - 优先点击的按钮文本。
         * @param {AbortSignal} [signal] - 任务中断信号。
         * @returns {Promise<number>} - 成功关闭的弹窗数量。
         */
        async findPageCloseAllPopups(buttonText = '取消', signal) {
            let closedCount = 0;
            
            // 1. 查找所有弹窗容器
            // 注意：document.querySelectorAll 是同步操作，不受 async/await 影响
            const popupContainers = document.querySelectorAll('.adm-center-popup-wrap');
            
            if (popupContainers.length === 0) {
                //Logger.info('未发现需要关闭的弹窗 (.adm-center-popup-wrap)。');
            }

            // 2. 遍历并点击关闭按钮
            for (let i = 0; i < popupContainers.length; i++) {
                // 必须在循环开始时进行中断检查
                if (signal && signal.aborted) {
                    //Logger.warn('closeAllPopups 任务中断。');
                    return closedCount;
                }

                const popupContainer = popupContainers[i];
                const buttons = popupContainer.querySelectorAll('button');
                let targetButton = null;
                let finalButtonText = null;

                // 辅助函数：根据文本查找按钮 (忽略空格)
                const findButton = (text) => {
                    for (const button of buttons) {
                        const span = button.querySelector('span');
                        if (span && span.textContent.replace(/\s+/g, '').trim() === text) {
                            finalButtonText = text;
                            return button;
                        }
                    }
                    return null;
                };

                // 查找优先级: 
                // a. 用户指定文本
                targetButton = findButton(buttonText);
                // b. 尝试 "确定" 按钮
                if (!targetButton) {
                    targetButton = findButton('确定');
                }
                // c. 尝试 "取消" 按钮
                if (!targetButton) {
                    targetButton = findButton('取消');
                }
                // 3. 执行点击和等待
                if (targetButton) {
                    const index = i + 1;
                    
                    Logger.info(`弹窗 ${index}/${popupContainers.length}：点击 "${finalButtonText}" 按钮关闭...`);
                    targetButton.click();
                    closedCount++;
                    
                    // 每次点击后短暂等待，让 UI 框架完成关闭
                    try {
                        await this.sleep(300, signal);
                    } catch (e) {
                        // 如果任务中断，直接退出
                        return closedCount;
                    }
                } else {
                    Logger.warn(`弹窗 ${i + 1}/${popupContainers.length}：未找到可点击的关闭按钮，跳过。`);
                }
            }
            
            // 4. 后备清理：调用 clickPopupMask 处理残留的遮罩层 (.adm-mask)
            //Logger.info('尝试使用 clickPopupMask 清理残留的遮罩层...');
            await this.findPageClickPopupMask(signal);
            
            return closedCount;
        },

        /**
         * 执行补充提交操作
         * @param {number} lasttija - 当前提交次数计数器
         * @param {AbortSignal} signal - 中断信号
         * @returns {Promise<number>} 0表示补充提交无效，1表示补充成功
         */
        async executeSupplementSubmit(signal) {
            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }

            // 查找文本框
            let textArea = document.querySelector('.adm-form-item-child-inner > .adm-text-area > .adm-text-area-element');
            if (!textArea) {
                const textAreas = document.querySelectorAll('.adm-text-area-element');
                for (const element of textAreas) {
                    if (element.offsetParent !== null) { // 检查是否可见
                        textArea = element;
                        break;
                    }
                }
            }

            // 查找提交按钮
            const submitBtn = Array.from(document.querySelectorAll('button')).find(btn =>
                btn.textContent.replace(/\s+/g, '').includes('提交')
            );

            // 判断提交按钮是否禁用
            const isSubmitDisabled = submitBtn ? submitBtn.disabled : true;

            // 检查文本框是否存在有效的JSON内容
            let hasJsonContent = false;
            if (textArea && textArea.value) {
                const dataSize = new Blob([textArea.value]).size;
                if (dataSize > 1024 * 1024) { // 1MB限制
                    Logger.warn('数据量过大，跳过JSON验证');
                    hasJsonContent = false;
                } else {
                    try {
                        JSON.parse(textArea.value);
                        hasJsonContent = true;
                    } catch (e) {
                        hasJsonContent = false;
                    }
                }
            }

            // 如果文本框存在有效JSON代码，且提交按钮没有禁用状态，则进行点击提交按钮
            if (hasJsonContent && !isSubmitDisabled && submitBtn) {
                // 点击提交按钮
                submitBtn.click();
                // 等待1.2秒
                await this.sleep(1200, signal); 
                
                // 处理提交后的确认弹窗
                const confirmClosedCount = await this.findPageCloseAllPopups('确定', signal); 
                
                if (confirmClosedCount > 0) {
                    Logger.info('补充提交题目');
                    await this.sleep(3000, signal); 
                    // 补充提交成功
                    return 1;
                } else {
                    Logger.warn('未找到提交后的确认按钮');
                    // 补充提交无效
                    return 0;
                }
            } else {
                // 检查具体失败原因并记录日志
                /*
                if (!submitBtn) {
                    Logger.error('未找到提交按钮，请手动提交');
                } else if (isSubmitDisabled) {
                    Logger.warn('提交按钮处于禁用状态，无法提交');
                } else if (!hasJsonContent) {
                    Logger.warn('文本框中无有效JSON内容，跳过提交');
                }*/

                // 补充提交无效
                if(isSubmitDisabled && hasJsonContent) {
                    Logger.warn('按钮不可点击,提交框中有数据代码');
                    return 2;
                }

                // 补充提交无效
                return 0;
            }
        },

        /**
         * 通过API 搜索酒店 ID 和 URL，支持 POST/GET 回退和任务中断。
         * @param {string} keyword - 酒店关键词。
         * @param {string} cityName - 城市名称。
         * @param {AbortSignal} [signal] - 任务中断信号。
         * @returns {Promise<{id: number, url: string}>}
         */
        async findApiBysearchHotels(keyword, cityName, signal) {
            const userAgent = navigator.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36';

            // 预处理关键词，使用集成后的同步方法
            const keywordHalfWidth = this.toHalfWidth(keyword);
            const keywordMain = this.extractMainName(keywordHalfWidth);
            const keywordBranch = keywordHalfWidth.replace(keywordMain, '').trim();

            // --- 1. 酒店匹配逻辑 (同步) ---
            const matchHotels = (result, isPostMethod) => {
                if (!result) {
                    Logger.error('数据格式不正确');
                    return { id: 0, url: '' };
                }

                let hotels = [];
                // 根据 POST/GET 结果解析数据结构
                if (isPostMethod) {
                    if (!result.Response || !Array.isArray(result.Response.searchResults)) return { id: 0, url: '' };
                    hotels = result.Response.searchResults.filter(item => item.type === 'Hotel');
                } else {
                    if (!result.data || !Array.isArray(result.data)) return { id: 0, url: '' };
                    hotels = result.data.filter(item => item.type === 'hotel');
                }

                if (hotels.length === 0 || !cityName) return { id: 0, url: '' };

                // 标准化城市名称
                const normalizedCityName = this.toHalfWidth(cityName).trim().toLowerCase();

                // 过滤同城市酒店 (匹配逻辑与原代码一致)
                const cityHotels = hotels.filter(hotel => {
                    if (!hotel.cityName) return false;
                    const normalizedHotelCity = this.toHalfWidth(hotel.cityName).trim().toLowerCase();
                    return normalizedHotelCity.includes(normalizedCityName) || 
                        normalizedCityName.includes(normalizedHotelCity);
                });
                
                // 匹配逻辑 1-4 (使用 this.jaroWinklerSimilarity 等辅助方法)
                // 1. 同城市精确匹配
                const exactMatch = cityHotels.find(hotel => this.toHalfWidth(hotel.word) === keywordHalfWidth);
                if (exactMatch) return { id: exactMatch.id, url: exactMatch.url || ('https://hotels.ctrip.com/hotels/' + exactMatch.id + '.html') };

                // 2. 同城市主体相似匹配（分店加权）
                let bestHotel = null;
                let bestScore = 0;
                cityHotels.forEach(hotel => {
                    const hotelHalf = this.toHalfWidth(hotel.word);
                    const hotelMain = this.extractMainName(hotelHalf);
                    if (hotelMain !== keywordMain) return; 

                    const hotelBranch = hotelHalf.replace(hotelMain, '').trim();
                    const branchSim = hotelBranch ? this.jaroWinklerSimilarity(hotelBranch, keywordBranch) : 0;
                    const mainSim = hotelBranch ? 0.7 : this.jaroWinklerSimilarity(hotelMain, keywordMain); 
                    const score = hotelBranch ? (0.7 * 1 + 0.3 * branchSim) : mainSim;
                    
                    if (score > bestScore) {
                        bestScore = score;
                        bestHotel = hotel;
                    }
                });
                if (bestHotel && bestScore > 0.85) return { id: bestHotel.id, url: bestHotel.url || ('https://hotels.ctrip.com/hotels/' + bestHotel.id + '.html') };

                // 3. 不同城市精确匹配
                const crossExact = hotels.find(hotel => this.toHalfWidth(hotel.word) === keywordHalfWidth);
                if (crossExact) return { id: crossExact.id, url: crossExact.url || ('https://hotels.ctrip.com/hotels/' + crossExact.id + '.html') };

                // 4. 不同城市主体相似匹配（分店加权）
                let crossBest = null;
                let crossScore = 0;
                hotels.forEach(hotel => {
                    const hotelHalf = this.toHalfWidth(hotel.word);
                    const hotelMain = this.extractMainName(hotelHalf);
                    if (hotelMain !== keywordMain) return;

                    const hotelBranch = hotelHalf.replace(hotelMain, '').trim();
                    const branchSim = hotelBranch ? this.jaroWinklerSimilarity(hotelBranch, keywordBranch) : 0;
                    const mainSim = hotelBranch ? 0.7 : this.jaroWinklerSimilarity(hotelMain, keywordMain);
                    const score = hotelBranch ? (0.7 * 1 + 0.3 * branchSim) : mainSim;

                    if (score > crossScore) {
                        crossScore = score;
                        crossBest = hotel;
                    }
                });
                if (crossBest && crossScore > 0.85) return { id: crossBest.id, url: crossBest.url || ('https://hotels.ctrip.com/hotels/' + crossBest.id + '.html') };

                return { id: 0, url: '' };
            };

            // --- 2. GET 方法回退 (Async) ---
            const fallbackToGetSearch = async () => {
                const url = 'https://m.ctrip.com/restapi/soa2/26872/search';
                const params = new URLSearchParams({
                    action: 'online', source: 'globalonline', keyword: keyword
                });
                const fullUrl = url + '?' + params.toString();
                
                Logger.info('再次匹配酒店');
                
                try {
                    const response = await this.makeHttpRequest(fullUrl, {
                        method: 'GET',
                        headers: { 'Content-Type': 'application/json', 'User-Agent': userAgent }
                    }, signal);
                    
                    const result = await response.json();
                    return matchHotels(result, false);
                    
                } catch (error) {
                    if (error.message && error.message.includes('aborted')) throw error;
                    Logger.error('GET 方法分析数据时出错: ' + error.message);
                    throw error;
                }
            };
            
            // --- 3. POST 方法主体 (Async) ---
            const url2 = 'https://m.ctrip.com/restapi/soa2/21881/json/gaHotelSearchEngine';
            const requestBody = {
                "keyword": keyword, "label": "", "searchType": "D", "cityId": 0, "district": 0, "province": 0, "platform": "online", "pageID": "102001",
                "head": { 
                    "Version": "", "userRegion": "CN", "Locale": "zh-CN", "LocaleController": "zh_cn", "TimeZone": "8", "Currency": "CNY", "PageId": "102001", "webpSupport": false, "userIP": "", "P": "", "ticket": "", 
                    "clientID": "09031027219053859313", "group": "ctrip", 
                    "Frontend": { "vid": "1752585643430.5968ZoEgnHyH", "sessionID": 162, "pvid": 8 }, 
                    "Union": { "AllianceID": "", "SID": "", "Ouid": "" }, 
                    "HotelExtension": { "group": "CTRIP", "hasAidInUrl": false, "WebpSupport": false }
                }
            };
            
            try {
                Logger.info('开始匹配酒店信息');
                
                const response = await this.makeHttpRequest(url2, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'User-Agent': userAgent },
                    body: JSON.stringify(requestBody),
                }, signal);

                const result = await response.json();
                const postResult = matchHotels(result, true);

                if (postResult.id !== 0) {
                    Logger.info(`匹配酒店完成`);
                    return postResult;
                }

                // POST 找到了数据，但匹配失败，继续回退
                return await fallbackToGetSearch();

            } catch (error) {
                if (error.message && error.message.includes('aborted')) throw error;
                Logger.error('POST 方法出错: ' + error.message + '，回退到 GET 方法');
                // POST 请求失败或解析失败，回退到 GET 
                return await fallbackToGetSearch(); 
            }
        },

        /**
         * 查询并通过率数据并从中提取合格率、通过数和拒绝数。
         *
         * @param {AbortSignal} [signal] - 任务中断信号，用于取消 fetch 请求。
         * @returns {Promise<object>} - 包含 passratio, reject, pass 的对象，失败时返回全零对象。
         */
        async findApiExtractPassRate(signal) {
            // 定义默认的失败返回值
            const defaultResult = { passratio: 0, reject: 0, pass: 0 };

            try {
                // 1. 发送请求，并传入 signal 实现可中断
                const response = await this.makeHttpRequest('https://frontend.lobaobao97.com/api/statement/query', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                }, signal);
                // 2. 检查 HTTP 响应状态
                if (!response.ok) {
                    throw new Error('获取通过率数据失败: HTTP ' + response.status);
                }

                // 3. 解析 JSON 数据
                const data = await response.json();

                // 4. 检查业务状态码和数据有效性
                if (data.status === 200 && data.statement_list && data.statement_list.length > 0) {
                    
                    // 查找 check_status 为 "wait_check" 的记录，否则使用第一条记录
                    const waitCheckStatement = data.statement_list.find(item => item.check_status === "wait_check");
                    const targetStatement = waitCheckStatement || data.statement_list[0];

                    let passRatio = 0;
                    let passCount = 0;
                    let rejectCount = 0;

                    // 5. 尝试解析 work_info 字段
                    if (targetStatement.work_info) {
                        try {
                            const workInfo = JSON.parse(targetStatement.work_info);
                            
                            if (Array.isArray(workInfo) && workInfo.length > 0) {
                                const personalInfo = workInfo[0];
                                
                                // 提取所需数据，使用 || 0 确保数值类型
                                passRatio = personalInfo.item_check_pass_ratio || 0;
                                rejectCount = personalInfo.item_check_reject_count || 0;
                                passCount = personalInfo.item_check_pass_count || 0; 
                            }
                        } catch (e) {
                            // ⚠️ 注意：假设 Logger 是 Scheduler 实例上的属性 (this.Logger)
                            Logger.error('解析 work_info 数据失败: ' + e.message);
                            // 解析失败，使用默认的 0/0/0
                        }
                    }
                    
                    // 6. 返回提取结果
                    return {
                        passratio: passRatio,
                        reject: rejectCount,
                        pass: passCount
                    };
                } if(data.status === 401) {
                    Logger.warn('当前任务账号已掉登,5秒刷新页面');
                    await this.sleep(5000, signal);
                    window.location.reload();
                    return defaultResult;
                } else {
                    Logger.warn('未获取到有效的通过率数据或状态码非 200');
                    return defaultResult;
                }

            } catch (error) {
                // 7. 统一错误处理
                if (error.name === 'AbortError') {
                    Logger.warn('获取通过率数据任务被中断。');
                    // 抛出 AbortError 允许上层 taskRunner 停止任务流程
                    throw error; 
                }
                console.error('获取通过率数据时出错: ' + error.message);
                
                // 抛出其他错误，让上层调用者决定如何处理，或直接返回 defaultResult
                // 为了兼容原 Promise 链的 rethrow 行为：
                throw error;
            }
        },

        async taskTracked(hotelId, action, city, signal) {
            var tracked = this.getConfig(this.TASK_TRACKED_KEY);
            // 读取已追踪的酒店ID列表
            var hid = tracked.hid;
            var uid = tracked.uid || this.generateUniqueID();
            var hidtime = tracked.hidtime || 0; //耗时计算
            var donecity = tracked.donecity || 0;
            var donecitylist = tracked.donecitylist || [];
            var donetask = tracked.donetask || 0;
            var switchtask = tracked.switchtask || 0; //记录切换城市时的任务数
            var runcity = tracked.runcity || 0; //记录是否第一次运行切换城市
            var canacct = tracked.canacct || ''; //记录当前运行账号信息
            var querytime = tracked.querytime || 0; //记录上次查询时间戳
            var reject = tracked.reject || 0;  //记录拒绝的任务数
            var passratio = tracked.passratio || 0; //记录通过率
            var canacctlist = tracked.canacctlist || {}; //记录账号信息取消信息
            var cantask = canacctlist[canacct] || 0; //记录取消的任务数
            var waittask = tracked.waittask || 0; //休息任务数

            var changed = false;
            //console.log('追踪任务前的数据:', action, hotelId, city, JSON.stringify(tracked));
            
            if (action === 'add') {
                // 添加酒店ID到追踪列表（如果不存在）
                if (!hid || hid !== hotelId) {
                    hid = hotelId;
                    hidtime = Date.now();
                    changed = true;
                    //Logger.info('已添加酒店ID ' + hid + ' 到追踪列表');
                }
            } else if (action === 'remove') {
                // 从追踪列表中移除酒店ID（如果存在）
                if (hid && hid === hotelId) {
                    hid = '';
                    changed = true;
                    donetask = donetask + 1;
                    //当前领取任务并执行成功后，但是城市还是0需要记录城市切换
                    if(donecity === 0) {
                        donecity = 1;
                        switchtask = donetask;
                        donecitylist = [];
                        donecitylist.push(city);
                    }
                    //记录耗时多少秒并打印
                    if(hidtime > 0) {
                        var hidtime_ = Date.now() - hidtime;
                        //记录耗时多少秒并打印
                        var hidtime_ = (Date.now() - hidtime) / 1000;
                        Logger.info('题目完成，耗时: ' + hidtime_.toFixed(2) + '秒');
                    }
                    //移除任务缓存
                    this.setConfig(this.TASK_KEY, {}, 8);
                    //Logger.info('已从追踪列表中移除酒店ID ' + hid);

                    //记录下次任务延迟时间
                    if(waittask === 0){
                        const config = this.getConfig(this.ACCOUNT_KEY);
                        //随机生成中间数
                        var min = config.counttask;
                        var max = config.counttaskMax;
                                                
                        if(min > 0 && max >= min){
                            var delaytask = Math.floor(Math.random() * (max - min + 1)) + min;
                            waittask = donetask + delaytask;
                        }
                    }
                }
            } else if (action === 'abnormal') {
                // 从追踪列表中移除酒店ID（如果存在）
                if (hid && hid === hotelId) {
                    hid = '';
                    changed = true;
                    //移除任务缓存
                    this.setConfig(this.TASK_KEY, {}, 8);
                    //Logger.info('异常移除酒店ID ' + hid);
                }
            } else if (action === 'check') {
                // 检查酒店ID是否在追踪列表中
                return hid === hotelId;
            } else if (action === 'changeacct') {
                canacct = hotelId;
                changed = true;
            } else if (action === 'changecity') {
                // 切换城市，重置追踪列表, 如果切换城市时任务数有变化则记录
                if(donetask > 0 && switchtask !== donetask && donecitylist.indexOf(city) === -1) {
                    donecity = donecity + 1;
                    donecitylist.push(city);
                    switchtask = donetask;
                    changed = true;
                }
                if(runcity === 0) {
                    runcity = 1;
                    changed = true;
                }
            } else if (action === 'reset') {
                // 重置追踪列表
                donecity = 0;
                donetask = 0;
                donecitylist= [];
                switchtask = donetask;
                runcity = 0;
                waittask = 0;
                changed = true;
            } else if (action === 'waittask') {
                // 检查酒店ID是否在追踪列表中
                waittask = 0;
                changed = true;
            } else if (action === 'cancel') {
                var config = this.getConfig(this.ACCOUNT_KEY);

                //初次记录cancel账号
                if(canacct === '' && config && config.uname) {
                    canacct = config.uname;
                }

                //如果账号相同则记录取消次数
                if(canacct !== '') {
                    canacctlist[canacct] = cantask + 1;
                }

                // 从追踪列表中移除酒店ID（如果存在）
                hid = '';
                changed = true;

                //移除任务缓存
                this.setConfig(this.TASK_KEY, {}, 8);
            } else if (action === 'passratio') {
                //查询通过率 根据 querytime 判断5分钟查询一次
                var currentTime = Date.now();
                var fiveMinutes = 1 * 60 * 1000; // 1分钟
                fiveMinutes = 10 * 1000; // 1分钟
                // 如果是第一次查询(querytime为0)或距离上次查询超过5分钟，则执行查询
                if (querytime === 0 || (currentTime - querytime) >= fiveMinutes) {
                    var config = this.getConfig(this.ACCOUNT_KEY);

                    try {
                        // 1. 调用 TaskManager.queryAndExtractPassRate 并等待结果，传入 signal 实现可中断
                        const result = await this.findApiExtractPassRate(signal);
                        // 2. 从结果中提取通过率信息
                        passratio = result.passratio;
                        reject = result.reject;
                        querytime = currentTime; // 假设 currentTime 在此作用域内可用

                        // 3. 初次记录 cancel 账号
                        // 假设 canacct 和 cached 在此作用域内可用
                        if (canacct === '' && config && config.uname) {
                            canacct = config.uname;
                        }

                        changed = true;
                    } catch (error) {
                        // 5. 错误处理
                        
                        // 如果是 AbortError，向上抛出，让顶层 taskRunner 统一处理任务停止
                        if (error.name === 'AbortError') {
                            Logger.warn('查询通过率任务被中断。');
                            throw error;
                        }
                        
                        // 非中断错误，根据原逻辑返回 false
                        console.error('查询通过率时出错: ' + error.message); // 原始逻辑可能不需要日志
                        return false;
                    }
                }
            }
            
            // 如果有变化，保存更新后的列表
            if (changed) {
                tracked = {
                    uid: uid,
                    hid: hid, 
                    hidtime: hidtime,
                    donecity: donecity, 
                    donetask: donetask, 
                    switchtask: switchtask, 
                    donecitylist: donecitylist, 
                    runcity: runcity, 
                    canacctlist: canacctlist, 
                    canacct: canacct,
                    querytime: querytime,
                    reject: reject,
                    passratio: passratio,
                    cantask: cantask,
                    waittask: waittask
                };
                //console.log('保存追踪列表: ' + JSON.stringify(tracked));
                this.setConfig(this.TASK_TRACKED_KEY, tracked, 8);

                // 同步更新面板显示
                this.updateDonetaskAndDonecity(donetask, donecity);
            }
            return true;
        },

        /**
         * 执行废弃酒店任务的完整流程：点击“废弃” -> 选择原因 -> 提交。
         * @returns {Promise<boolean>} - 任务是否成功提交。
         * @param {AbortSignal} [signal] - 任务中断信号。
         */
        async findPageByGiveupHotels(signal) {
            // ------------------------------------
            // 第零步：查找并点击“废弃”按钮
            // ------------------------------------
            const abandonSpan = Array.from(document.querySelectorAll('button span')).find(span =>
                span.textContent.replace(/\s+/g, '').includes('废弃')
            );

            if (!abandonSpan) {
                Logger.error('未找到废弃按钮');
                return false;
            }

            // 点击按钮（使用 closest('button') 更安全，但为了兼容原代码结构，点击 span 的父级 button）
            const abandonButton = abandonSpan.closest('button') || abandonSpan;
            abandonButton.click();
            Logger.info('点击废弃按钮');

            try {
                // ------------------------------------
                // 第一步：等待弹窗出现，查找并点击“废弃原因”选择区域
                // ------------------------------------
                await this.sleep(800, signal);

                // 查找废弃原因标签
                const reasonLabel = Array.from(document.querySelectorAll('.adm-form-item-label')).find(label =>
                    label.textContent.replace(/\s+/g, '').includes('废弃原因')
                );

                // 查找“请选择”区域（即输入框/选择器的子元素）
                const reasonSelector = reasonLabel
                    ? reasonLabel.closest('.adm-form-item').querySelector('.adm-form-item-child-inner')
                    : null;

                if (!reasonSelector) {
                    Logger.error('未找到废弃原因选择区域');
                    return false;
                }

                reasonSelector.click();
                // Logger.info('点击废弃原因选择区域'); // 减少日志噪音

                // ------------------------------------
                // 第二步：等待下拉列表出现，选择第一个选项
                // ------------------------------------
                await this.sleep(1200, signal);

                // 查找并点击下拉列表中的第一个选项
                const firstOption = document.querySelector('.adm-picker-view-item-height-measure');

                if (firstOption) {
                    firstOption.click();
                    Logger.info('选择第一个废弃原因');
                } else {
                    Logger.warn('未找到第一个废弃原因选项，尝试继续流程...');
                }

                // ------------------------------------
                // 第三步：等待选择完成，点击下拉列表的“确定”按钮
                // ------------------------------------
                await this.sleep(800, signal);

                // 查找包含 Picker 的容器，以定位其内部的“确定”按钮
                const pickerContainer = document.querySelector('.adm-picker');
                const pickerConfirmBtn = pickerContainer
                    ? Array.from(pickerContainer.querySelectorAll('.adm-picker-header a')).find(a =>
                        a.textContent.replace(/\s+/g, '').trim() === '确定'
                    )
                    : null;

                if (!pickerConfirmBtn) {
                    Logger.error('未找到下拉列表确定按钮');
                    return false;
                }

                pickerConfirmBtn.click();
                // Logger.info('点击下拉列表确定按钮');

                // ------------------------------------
                // 第四步：等待弹框更新，点击“提交”按钮
                // ------------------------------------
                await this.sleep(800, signal);

                // 查找对话框容器中的“提交”按钮
                const dialogContainer = document.querySelector('.adm-center-popup-body.adm-dialog-body');
                let submitBtn = null;

                if (dialogContainer) {
                    submitBtn = Array.from(dialogContainer.querySelectorAll('button')).find(btn =>
                        btn.textContent.replace(/\s+/g, '').trim() === '提交'
                    );
                }

                if (!submitBtn) {
                    Logger.error('未找到提交按钮');
                    return false;
                }

                submitBtn.click();
                Logger.info('点击废弃提交按钮');

                // 记录废弃次数
                this.taskTracked('', 'cancel', '', signal);
                return true;

            } catch (error) {
                // 如果任务被中断（来自 this.sleep），抛出错误，否则记录并返回 false
                if (error.message && error.message.includes('aborted')) {
                    throw error;
                }
                Logger.error('执行废弃流程时出错: ' + error.message);
                return false;
            }
        },

        /**
         * 根据任务数据和模式打开新的任务窗口。
         * @param {object} task - 任务数据，包含 hotelId, checkin, checkout, cityName, hotelUrl 等。
         * @param {number} mode - 打开模式：1 (默认逻辑) 或 2 (CityID/CityEnName 优化逻辑)。
         */
        openTaskWindow (task, mode) {
            // 1. 日期计算
            const today = new Date();
            const targetDate = new Date(task.checkin);
            
            // 检查是否为同一天
            const isSameDate = today.getFullYear() === targetDate.getFullYear() &&
                            today.getMonth() === targetDate.getMonth() &&
                            today.getDate() === targetDate.getDate();

            // 记录日志
            Logger.info((isSameDate ? '今日题目' : '非今日题目') + `(${mode}): ${task.hotel}，${task.checkin} ~ ${task.checkout}`);

            let url;
            
            // --- Mode 1: 默认打开方式 ---
            if (mode == 1) {
                if (task.hotelUrl && task.hotelUrl !== '') {
                    // 使用 hotelUrl
                    const separator = task.hotelUrl.includes('?') ? '&' : '?';
                    if (isSameDate) {
                        url = task.hotelUrl;
                    } else {
                        url = task.hotelUrl + separator + 'checkIn=' + task.checkin + '&checkOut=' + task.checkout;
                    }
                } else {
                    // 使用携程默认链接
                    const baseCtripUrl = 'https://hotels.ctrip.com/hotels/' + task.hotelId + '.html';
                    if (isSameDate) {
                        url = baseCtripUrl;
                    } else {
                        url = baseCtripUrl + '?checkIn=' + task.checkin + '&checkOut=' + task.checkout;
                    }
                }
            }

            // --- Mode 2: CityID/CityEnName 优化打开方式 ---
            if (mode == 2) {
                let cityName = task.cityName || '';
                // 去掉最后一个“市”字
                if (cityName.endsWith('市')) {
                    cityName = cityName.slice(0, -1);
                }

                // 匹配 cityList
                const cityInfo = GLOBAL_PARAMS.cityList.find(function(item) {
                    return item.name === cityName;
                });

                // 基础 URL 部分
                const baseQuery = '&hotelId=' + task.hotelId +
                                '&adult=1&crn=1&children=0&highprice=-1&lowprice=0&listfilter=1';

                if (cityInfo) {
                    // 匹配到城市，拼接 cityid 和 nameEn
                    const dateQuery = '&checkIn=' + task.checkin + '&checkOut=' + task.checkout;
                    url = 'https://hotels.ctrip.com/hotels/detail/?cityEnName=' + cityInfo.nameEn +
                        '&cityId=' + cityInfo.id +
                        dateQuery +
                        baseQuery;
                } else {
                    // 匹配不到城市，使用默认携程详情页链接
                    const baseDetailUrl = 'https://hotels.ctrip.com/hotels/detail/?';
                    
                    if (isSameDate) {
                        // 默认日期逻辑：不带 checkIn/checkOut
                        url = baseDetailUrl + baseQuery.substring(1); // 去掉开头的 &
                    } else {
                        // 非今日日期逻辑：带 checkIn/checkOut
                        const dateQuery = 'checkIn=' + task.checkin + '&checkOut=' + task.checkout;
                        url = baseDetailUrl + dateQuery + baseQuery;
                    }
                }
            }
            
            // 3. 打开新窗口 (只有在 mode 1 或 mode 2 匹配到 URL 时执行)
            if (url) {
                window.open(url, '_blank');
            } else {
                Logger.error(`未找到有效的打开模式 (${mode}) 或 URL 缺失，无法打开新窗口。`);
            }
        },

        /**
         * 执行城市选择逻辑，支持优先级和最大城市数限制。
         * @param {string} cityName - 当前城市名称，用于确定下一个城市。
         * @param {number} [preIndex=-1] - 上一个城市在列表中的索引，用于顺序切换.
         * @param {AbortSignal} signal - 任务中断信号。
         * @returns {Promise<{success: boolean, reason?: string, selectedCityName?: string}>}
         */
        async findPageSelectCity(cityName, preIndex = -1, signal) {

            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }

            // 1. 查找并点击 '选择城市' 按钮
            var cityButtonSpans = document.querySelectorAll('button span');
            var cityButtonSpan = null;
            
            for (var i = 0; i < cityButtonSpans.length; i++) {
                if (cityButtonSpans[i].textContent.trim() === '选择城市') {
                    cityButtonSpan = cityButtonSpans[i];
                    break;
                }
            }
            
            if (!cityButtonSpan) {
                return { success: false, reason: 'no_city_button' };
            }
            
            cityButtonSpan.click();
            Logger.info('打开城市下拉框');
            
            // 2. 等待弹窗出现
            try {
                await this.sleep(1500, signal);
            } catch (e) {
                return { success: false, reason: 'task_aborted' };
            }

            // 3. 获取配置和状态
            const config = this.getConfig(this.ACCOUNT_KEY);
            const taskTracked = this.getConfig(this.TASK_TRACKED_KEY);
            
            const maxCity = parseInt(config.mcity) || 3;
            const donecitylist = taskTracked.donecitylist || [];
            
            // 处理用户设置的优先城市列表（使用逗号或 | 分隔）
            let priorityCities = [];
            if (config.priorityCities) {
                priorityCities = config.priorityCities
                    .split(/[|,]/)
                    .map(city => city.trim().replace(/[\uFF01-\uFF5E]/g, (match) => 
                    String.fromCharCode(match.charCodeAt(0) - 0xFEE0)))
                    .filter(city => city.length > 0);
            }
            
            // 4. 筛选可用城市元素
            var cityItems = document.querySelectorAll('.adm-check-list-item');
            var availableCities = []; // 所有有题目的城市
            var priorityAvailableCities = []; // 在优先列表中的有题目城市
            
            for (var item of cityItems) {
                var mainContent = item.querySelector('.adm-list-item-content-main');
                
                if (mainContent && mainContent.textContent.indexOf('暂无题目') === -1) {
                    var cityNameText = mainContent.textContent.trim().replace('暂无题目', '');
                    var normalizedCityName = cityNameText.replace(/[\uFF01-\uFF5E]/g, (match) =>  String.fromCharCode(match.charCodeAt(0) - 0xFEE0));
                    
                    const cityData = {
                        element: item,
                        name: normalizedCityName
                    };

                    availableCities.push(cityData);

                    // 检查是否为优先城市
                    if (priorityCities.length > 0 && priorityCities.some(p => normalizedCityName.includes(p) || p.includes(normalizedCityName))) {
                        priorityAvailableCities.push(cityData);
                    }
                }
            }

            // 5. 检查可用性
            if (availableCities.length === 0) {
                await this.sleep(1200, signal); // 等待完成
                Logger.info('当前无可用城市');
                await this.findPageClickPopupMask(signal);
                return { success: false, reason: 'no_available_cities' };
            }
            
            var selectedCity = null;
            
            // 6. 城市选择逻辑
            if (donecitylist.length >= maxCity) {
                // A. 达到最大城市数限制，循环已切城市
                var availableDoneCities = availableCities.filter(c => donecitylist.includes(c.name));
                var availableDoneCityNames = availableDoneCities.map(c => c.name);
                
                Logger.info(`已切城市达最大数 ${donecitylist.length}/${maxCity}`);
                Logger.info(`已切城市：${availableDoneCityNames.length > 0 ? JSON.stringify(availableDoneCityNames) : '无可用已切城市'}`);
                
                if (availableDoneCities.length > 0) {
                    var currentIndex = availableDoneCities.findIndex(c => c.name === cityName);
                    var nextIndex = (currentIndex + 1) % availableDoneCities.length;
                    selectedCity = availableDoneCities[nextIndex];
                } else {
                    // 没有匹配的已切换城市可用
                    await this.sleep(1200, signal); // 等待完成
                    await this.findPageClickPopupMask(signal);
                    return { success: false, reason: 'max_city_reached_no_available' };
                }
            } else {
                // B. 未达到最大城市数限制，选择未处理城市
                Logger.info(`当前城市数 ${donecitylist.length}/${maxCity}。`);
                
                let targetList = availableCities;
                
                // 优先使用用户设置的优先城市列表
                if (priorityCities.length > 0 && priorityAvailableCities.length > 0) {
                    targetList = priorityAvailableCities;
                    Logger.info('优先从用户指定城市列表中选择。');
                } else {
                    Logger.info('从所有可用城市列表中选择。');
                }

                // 如果可选城市在优先城市列表中，则无需切换
                /*
                if (targetList.some(city => city.name === cityName)) {
                    Logger.info('当前城市选择，无需切换。');
                    return { success: true, reason: 'no_need_to_switch' };
                }*/

                // 查找下一个未处理的城市
                let currentIndex = targetList.findIndex(c => c.name === cityName);
                if (preIndex > -1) {
                    currentIndex = preIndex;
                }

                let nextIndex = (currentIndex + 1) % targetList.length;
                let originalNextIndex = nextIndex;
                let foundNewCity = false;
                
                do {
                    const candidateCity = targetList[nextIndex];
                    if (!donecitylist.includes(candidateCity.name)) {
                        selectedCity = candidateCity;
                        foundNewCity = true;
                        break;
                    }
                    nextIndex = (nextIndex + 1) % targetList.length;
                    
                } while (nextIndex !== originalNextIndex);

                // 如果循环一周后仍未找到新城市，则继续循环已处理过的城市（确保任务继续）
                if (!foundNewCity) {
                    Logger.info('所有可用/优先城市均已在本轮处理过，继续循环已处理城市。');
                    nextIndex = (currentIndex + 1) % targetList.length;
                    selectedCity = targetList[nextIndex];
                }
            }

            // 7. 执行城市选择和状态更新
            if (selectedCity) {
                selectedCity.element.click();
                Logger.info(`已选择城市: ${selectedCity.name}`);
                
                await this.taskTracked('', 'changecity', selectedCity.name, signal);
                
                // 8. 等待切换完成
                try {
                    await this.sleep(1500, signal);
                    await this.findPageClickPopupMask(signal);
                } catch(e) {
                    return { success: false, reason: 'task_aborted_after_click' };
                }
                return { success: true, selectedCityName: selectedCity.name };
            } else {
                Logger.warn('切换城市失败');
                await this.findPageClickPopupMask(signal);
                return { success: false, reason: 'no_city_selected' };
            }
        },

        /**
         * 根据标签文本从特定 DOM 结构中提取任务详情。
         * 目标结构: .adm-form-item > .adm-form-item-label (包含 labelText) 
         * -> .adm-form-item-child-inner > span (包含值)
         * * @param {string} labelText - 标签文本（例如 '入住时间', '酒店名称'）。
         * @returns {string | null} - 提取到的文本或 null。
         */
        findPageTaskDetailText(labelText) {
            var items = document.querySelectorAll('.adm-form-item');
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                var label = item.querySelector('.adm-form-item-label');
                
                // 1. 查找匹配的标签
                // 移除标签内容中的所有空格（包括 &nbsp; 等）进行严格匹配
                if (label && label.textContent.replace(/\s+/g, '').trim() === labelText) {
                    // 2. 提取值所在的 span
                    var span = item.querySelector('.adm-form-item-child-inner span');
                    if (span) {
                        // 移除值中的所有空格，并返回
                        return span.textContent.replace(/\s+/g, '').trim();
                    }
                }
            }
            // 未找到
            return ;
        },

        /**
         * 检查当前页面是否存在任务详情，并尝试从缓存或 API 补齐缺失的酒店 ID。
         * 需要返回三种状态 0.没有题目信息 1.题目信息完整，2.题目信息完整但酒店id缺失
         * @param {string} cityName - 当前城市名称。
         * @returns {Promise<{cityName: string, checkin: string | null, checkout: string | null, hotel: string | null, hotelId: string | null, hotelUrl: string | null, state: int}>}
         */
        async findPageExistingTaskDetails(cityName) {
            // 1. 获取 DOM 信息 (假设 getTextFromSpanNearLabel 是同步的)
            const checkin = this.findPageTaskDetailText('入住时间');
            const checkout = this.findPageTaskDetailText('离店时间');
            const hotel = this.findPageTaskDetailText('酒店名称');
            let hotelId = this.findPageTaskDetailText('酒店id'); // 使用 let 允许修改

            //console.log('DOM 信息:', { checkin, checkout, hotel, hotelId });

            // 2. 检查所有字段是否在 DOM 中存在
            if (checkin && checkout && hotel && hotelId) {
                Logger.info(`题目信息: ${hotel}，${checkin}~${checkout}`);
                return { 
                    cityName: cityName, 
                    checkin: checkin, 
                    checkout: checkout, 
                    hotel: hotel, 
                    hotelId: hotelId, 
                    hotelUrl: null, 
                    state: 1
                };
            }

            // 3. 检查所有字段是否为空
            if(checkin === '' && checkout === '' && hotel === '' && hotelId === '') {
                return { 
                    cityName: cityName, 
                    checkin: null, 
                    checkout: null, 
                    hotel: null, 
                    hotelId: null, 
                    hotelUrl: null,
                    state: 0
                };
            }
            
            // 4. 检查缓存中是否有任务信息
            const task = this.getConfig(this.TASK_KEY) || {};
            
            // 如果缓存存在且与当前 DOM 中已获取的信息匹配
            if (task.checkin && task.checkout && task.hotel && task.hotelId &&
                task.checkin === checkin && 
                task.checkout === checkout && 
                task.hotel === hotel) {
                
                Logger.info(`待做题目: ${hotel}，${checkin}~${checkout}`);
                return { 
                    cityName: cityName, 
                    checkin: checkin, 
                    checkout: checkout, 
                    hotel: hotel, 
                    hotelId: task.hotelId, 
                    hotelUrl: task.hotelUrl || null,
                    state: 1
                };
            }
            
            // 5. 如果缺少 hotelId 但其他核心字段存在，则通过 API 搜索
            if (checkin && checkout && hotel && !hotelId) {
                //Logger.info(`缺少酒店ID，正在调用 searchHotels API 搜索: ${hotel} in ${cityName}...`);
                
                try {
                    // 【关键重构】使用 await 调用异步的 searchHotels 方法
                    const result = await this.findApiBysearchHotels(hotel, cityName);
                    
                    if (result && result.id > 0) {
                        const newHotelId = result.id + '';
                        const taskInfo = { 
                            cityName: cityName, 
                            checkin: checkin, 
                            checkout: checkout, 
                            hotel: hotel, 
                            hotelId: newHotelId, 
                            hotelUrl: result.url,
                            state: 1
                        };

                        this.setConfig(this.TASK_KEY, {
                            ...task,
                            checkin: checkin,
                            checkout: checkout,
                            hotel: hotel,
                            hotelId: newHotelId,
                            hotelUrl: result.url,
                            state: 1
                        }, 8);
                        
                        //Logger.info(`成功通过 API 补齐酒店信息。ID: ${newHotelId}`);
                        return taskInfo;
                    } else {
                        Logger.warn('匹配失败，未找到有效酒店');
                        // 继续执行到下一步，返回不完整信息
                    }
                } catch (error) {
                    // 捕获任务中断或API错误
                    if (error.message && error.message.includes('aborted')) throw error;
                    Logger.error('调用 API 出错: ' + error.message);
                    // 继续执行到下一步，返回不完整信息
                }
            }
            
            // 6. 其他情况
            /*
            if (checkin && checkout && hotel) {
                Logger.info(`页面信息不完整，无法开始任务。`);
            } else {
                Logger.info('页面上任务关键信息（入住/离店/酒店名）缺失。');
            }*/
            
            return { 
                cityName: cityName, 
                checkin: checkin, 
                checkout: checkout, 
                hotel: hotel, 
                hotelId: hotelId, 
                hotelUrl: null, 
                state: 2
            };
        },

        /**
         * 获取、解析、填入题目数据并执行提交。
         * * @param {object} userInfo - 用户信息。
         * @param {object} task - 当前任务数据（包含 hotelId, checkin 等）。
         * @param {AbortSignal} signal - 任务中断信号。
         * @returns {Promise<void>} - 任务流程完成或被中断。
         */
        async processTaskAndSubmit(voucherNo, task, signal) {
            // 检查任务是否在启动前已被中断（可选的快速退出机制）
            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }
            try {
                Logger.info('获取当前题目数据');
                
                // --- 步骤 1: 请求题目数据 ---
                const resp = await this.makeHttpRequest('https://www.jpzz.top/api/lobaobao/devast', {
                    method: 'POST',
                    credentials: 'omit',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voucherNo: voucherNo, ext: task.hotelId, checkin: task.checkin }),
                }, signal);

                const result = await resp.json();

                // --- 步骤 2: 结果处理和打开新窗口逻辑 ---
                if (result.code === 0 && task.state === 1) {
                    await this.taskTracked(task.hotelId, 'add', task.cityName, signal); // 清除追踪标识
                    this.openTaskWindow(task, 2);
                    return; // 流程结束
                }

                if (result.code !== 1 || !result.data) {
                    Logger.error(`获取题目数据失败，Code: ${result.code}, Data: ${result.data}`);
                    return; // 流程结束
                }
                
                // --- 步骤 3: 解密数据 ---
                const originalResData = await CryptoUtils.decrypt(result.data, task.hotelId);
                //Logger.info('解密完成');

                // --- 步骤 4: 解析 resData 并处理格式错误（废弃题目 1）---
                let resData = null;
                try {
                    resData = JSON.parse(originalResData);
                } catch (parseError) {
                    Logger.error('数据格式无效，执行废弃题目: ' + parseError.message);
                    const success = await this.giveupHotels(signal); // 必须 await
                    Logger.info(success ? '执行废弃题目完成' : '执行废弃题目失败');
                    return;
                }

                if (!resData.ext) {
                    Logger.error('未获取到分析数据（resData.ext缺失），请稍后再试');
                    return;
                }
                
                //Logger.info('解析当前题目数据');
                
                // --- 步骤 5: 解析 extData 并处理格式错误（废弃题目 2）---
                let extData = null;
                try {
                    // extData 即为 hotelData
                    extData = JSON.parse(resData.ext); 
                } catch (extParseError) {
                    Logger.error('分析数据无效，执行废弃题目: ' + extParseError.message);
                    const success = await this.findPageByGiveupHotels(signal);
                    Logger.info(success ? '执行废弃题目完成' : '执行废弃题目失败');
                    return;
                }

                // --- 步骤 6: 处理 extData 业务逻辑码 ---
                if (extData.code === 0) {
                    Logger.error('结果异常，停止运行，' + extData.message);
                    this.taskTracked(task.hotelId, 'abnormal', task.cityName);
                    this.stopTask();
                    return;
                }

                if (extData.code === 2) {
                    Logger.error('未获取到题目数据，放弃题目');
                    const success = await this.findPageByGiveupHotels(signal);
                    Logger.info(success ? '执行废弃题目完成' : '执行废弃题目失败');
                    return;
                }
                
                // --- 步骤 7: UI 积分更新 ---
                if (resData.avail) {
                    this.updateScores(resData.avail);
                }
                if (resData.duc > 0) {
                    Logger.info('当前可用积分: ' + resData.avail + '，本次消耗: ' + resData.duc);
                }
                
                // --- 步骤 8: 进一步数据校验（废弃题目 3）---
                /*
                if (extData.roomCount !== undefined && extData.roomCount === 0) {
                    Logger.warn('无效数据，执行废弃题目（roomCount=0）');
                    const success = await this.findPageByGiveupHotels(signal);
                    Logger.info(success ? '执行废弃题目完成' : '执行废弃题目失败');
                    return;
                }*/
                
                // --- 步骤 9: 最终解析 extData.ext (真正要填入的数据) ---
                let finalExtData = null;
                if (!extData.ext) {
                    Logger.error('缺少最终分析数据，无法继续。');
                    return;
                }
                try {
                    finalExtData = JSON.parse(extData.ext);
                } catch (finalParseError) {
                    Logger.error('最终分析数据无效，执行废弃题目: ' + finalParseError.message);
                    const success = await this.findPageByGiveupHotels(signal);
                    Logger.info(success ? '执行废弃题目完成' : '执行废弃题目失败');
                    return;
                }
                
                // --- 步骤 10: DOM 交互：填入数据 ---
                await this.sleep(1200, signal); 

                let textArea = document.querySelector('.adm-form-item-child-inner > .adm-text-area > .adm-text-area-element');
                if (!textArea) {
                    const textAreas = document.querySelectorAll('.adm-text-area-element');
                    for (const element of textAreas) {
                        if (element.offsetParent !== null) { // 检查是否可见
                            textArea = element;
                            break;
                        }
                    }
                }

                if (textArea) {
                    // 填入数据
                    textArea.value = JSON.stringify(finalExtData, null, 2);
                    
                    // 触发 input 事件
                    const inputEvent = document.createEvent ? document.createEvent('Event') : new Event('input');
                    if (document.createEvent) {
                        inputEvent.initEvent('input', true, true);
                    }
                    textArea.dispatchEvent(inputEvent);
                    Logger.info('执行数据填入文本框');

                    // --- 步骤 11: 检查并点击确认弹窗（前置检查）---
                    const closedCount = await this.findPageCloseAllPopups('确定', signal); 

                    if (closedCount > 0) {
                        Logger.info('已点击存在的确认按钮，跳过后续提交操作');
                        await this.sleep(2000, signal); 
                        return; // 流程结束
                    }

                    // --- 步骤 12: 查找并点击提交按钮 ---
                    const submitBtn = Array.from(document.querySelectorAll('button')).find(btn =>
                        btn.textContent.replace(/\s+/g, '').includes('提交')
                    );

                    if (submitBtn) {
                        submitBtn.click();
                        Logger.info('执行提交题目');
                        
                        await this.sleep(1200, signal); 
                        
                        // --- 步骤 13: 处理提交后的确认弹窗 ---
                        const confirmClosedCount = await this.findPageCloseAllPopups('确定', signal); 
                        
                        if (confirmClosedCount > 0) {
                            Logger.info('执行提交题目确认');
                            await this.taskTracked(task.hotelId, 'remove', task.cityName, signal); // 清除追踪标识
                            await this.sleep(3000, signal); 
                            Logger.info('提交题目完成');
                        } else {
                            Logger.error('未找到提交后的确认按钮');
                        }
                    } else {
                        Logger.error('未找到提交按钮，请手动提交');
                    }
                } else {
                    Logger.error('执行数据填入文本框失败, 请手动填入');
                    Logger.info('页面上共有 ' + document.querySelectorAll('.adm-text-area-element').length + ' 个textarea元素');
                }

            } catch (error) {
                // --- 步骤 14: 统一错误和中断处理 ---
                if (error.name === 'AbortError' || error.message === 'Aborted') {
                    Logger.info('任务被中断退出。');
                    throw error; // 向上层抛出，让 taskRunner 停止
                }
                
                //Logger.error('执行分析数据流程时失败: ' + error.message);
                // 如果不是中断，流程继续或停止，取决于上层 taskRunner 的逻辑。
            }
        },

        /**
         * 执行自动任务版本：获取任务、解密、处理业务逻辑并执行页面操作。
         * @param {AbortSignal} signal - 任务中断信号。
         * @returns {Promise<void>}
         */
        async executeApiTask(signal) {
            Logger.info('执行自动任务版本.');

            // 检查任务是否在启动前已被中断（可选的快速退出机制）
            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }

            try {
                // --- 2. 同步 DOM 查询获取当前城市 ---
                let cityName = '';
                const cityButtonSpans = document.querySelectorAll('button span');
                let cityButtonSpan = null;
                
                for (const span of cityButtonSpans) {
                    if (span.textContent.trim() === '选择城市') {
                        cityButtonSpan = span;
                        break;
                    }
                }
                
                if (cityButtonSpan) {
                    let parent = cityButtonSpan.parentNode;
                    while (parent) {
                        if (parent.classList && parent.classList.contains('adm-space-item')) {
                            const buttonDiv = parent;
                            if (buttonDiv.nextElementSibling) {
                                cityName = buttonDiv.nextElementSibling.textContent.trim();
                            }
                            break;
                        }
                        parent = parent.parentNode;
                    }
                    
                }

                var config = this.getConfig(this.ACCOUNT_KEY) || {};
                var taskTracked = this.getConfig(this.TASK_TRACKED_KEY) || {};
                //var task = this.getConfig(this.TASK_KEY) || {};

                if(!taskTracked.uid){
                    taskTracked.uid = this.generateUniqueID();
                    this.setConfig(this.TASK_TRACKED_KEY, taskTracked, 8);
                }

                // --- 3. 提取追踪数据 ---
                var uid = taskTracked.uid;
                var hid = taskTracked.hid || '';
                var donetask = taskTracked.donetask || 0;
                var donecity = taskTracked.donecity || 0;
                var donecitylist = taskTracked.donecitylist || [];
                //console.log('任务追踪数据:', taskTracked);

                if(donecitylist.length > 0){
                    cityName = donecitylist[donecitylist.length -1];
                }

                Logger.info('当前城市：' + (cityName || ''));
                Logger.info(`已做题目:${donetask}/${config.mtask},已切城市:${donecity}/${config.mcity}`);

                // --- 4. 业务量限制检查 ---
                if (donetask >= config.mtask) {
                    Logger.warn(`当前量产数量超出${config.mtask}限制，停止运行！`);
                    this.stopTask();
                    return;
                }

                const resp = await this.makeHttpRequest('https://www.jpzz.top/api/lobaobao/apitask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: config.uname, v: config.upass, voucherNo: config.voucherNo, city: cityName, uid: uid }),
                    credentials: 'omit',
                    signal: signal // 注入 AbortSignal
                }, signal);

                const result = await resp.json();

                // --- 6. 解密和解析数据 ---
                if (result.code === 1 && result.data) {
                    const originalResData = await CryptoUtils.decrypt(result.data, config.uname);
                    
                    let resData = null;
                    try {
                        // 验证解密后的数据是否为有效的JSON格式
                        resData = JSON.parse(originalResData);
                    } catch (parseError) {
                        Logger.error('数据无效格式，JSON解析失败: ' + parseError.message);
                    }
                    
                    if (!resData || !resData.ext) {
                        Logger.error(resData ? '未获取到分析数据（resData.ext缺失），请稍后再试' : 'resData为null，流程停止');
                        return;
                    }

                    let extData = null;
                    try {
                        // 解析 extData
                        extData = JSON.parse(resData.ext);
                    } catch (extParseError) {
                        Logger.error('分析数据无效，JSON解析失败: ' + extParseError.message);
                        return; // 停止处理
                    }
                    
                    // --- 7. 业务逻辑处理 ---
                    if (extData.code === 0) {
                        Logger.error('结果异常:' + extData.message);
                        this.stopTask();
                        return;
                    }

                    // UI 更新和日志
                    if (resData.avail) {
                        this.updateScores(resData.avail);
                    }
                    if (resData.duc > 0) {
                        Logger.info(`当前可用积分: ${resData.avail}，本次消耗: ${resData.duc}`);
                    }
                    Logger.info(extData.message);

                    if (extData.total && extData.total > 0) {
                        Logger.info(`当前已做题目总数: ${extData.total}`);
                    }

                    // --- 8. 任务 URL 处理 ---
                    if (extData.url && extData.url !== '') {
                        // 延迟 3 秒 (可中断)
                        await this.sleep(3000, signal); 
                        //console.log('任务数据:', JSON.stringify(extData));
                        //if(hid !== '') {
                            //Logger.warn(`请检查账号配置是否重复配置`);
                            //return;
                        //}

                        this.taskTracked(extData.hotelId, 'add', extData.city, signal);
                        // 打开URL
                        window.open(extData.url, '_blank');
                        return;
                    }

                    // --- 9. 任务切换/覆盖逻辑 ---
                    if (extData.cover && extData.cover !== '') {
                        await this.taskTracked(extData.hotelId, 'changecity', extData.city, signal);
                        await this.taskTracked(extData.hotelId, 'remove', extData.city, signal);
                    }
                    // 原始代码在此处结束，隐式返回 Promise.resolve()
                } else {
                    Logger.error(`获取任务数据失败，Code: ${result.code} 或 Data 缺失。`);
                }

            } catch (e) {
                // --- 10. 统一错误和中断处理 ---
                if (e.name === 'AbortError' || e.message === 'Aborted') {
                    console.error('任务被用户中断退出。');
                    throw e; // 向上层抛出 AbortError，停止整个 taskRunner 流程
                }
                console.error('执行 executeApiTask 流程时失败: ' + e.message);
                // 对于非中断错误，不向上抛出，流程隐式结束。
            }
        },

        /**
         * 执行平台页面登录的操作。
         * @param {AbortSignal} signal - Task interruption signal.
         */
        async executePageLogin(signal) { 
            Logger.info('平台未登录，执行登录动作.');
            const config = this.getConfig(this.ACCOUNT_KEY);
            
            var userInput = document.querySelector('#account');
            var passInput = document.querySelector('#secret_key');
            
            if (userInput && passInput) {
                // 使用 getConfig 获取配置信息
                userInput.value = config.uname; 
                passInput.value = config.upass; 
                
                // 模拟输入事件
                var inputEvent = document.createEvent ? document.createEvent('Event') : new Event('input');
                if (document.createEvent) {
                    inputEvent.initEvent('input', true, true);
                }
                userInput.dispatchEvent(inputEvent);
                passInput.dispatchEvent(inputEvent);
                
                // 使用重构后的 findPageButtonByText
                await this.findPageButtonByText('登录', '进行登录中', '登录失败，请手动登录', 3000, signal);
                
            } else {
                 Logger.warn('未找到登录输入框,5秒后自动刷新');
                 await this.sleep(5000, signal);
                 window.location.href = GLOBAL_PARAMS.labaobaoHomeUrl
                 return;
            }
        },

        /**
         * 执行页面任务的操作。
         * @param {AbortSignal} signal - 任务中断信号。
         */
        async executePageTask(signal) { 
            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }

            const config = this.getConfig(this.ACCOUNT_KEY);
            var task = this.getConfig(this.TASK_KEY);
            var taskTracked = this.getConfig(this.TASK_TRACKED_KEY);

            await this.sleep(2000, signal); // 等待页面刷新完成

            //获取任务数量
            var spans = document.querySelectorAll('span');
            var drtmSpan = null;
            
            for (var i = 0; i < spans.length; i++) {
                if (spans[i].textContent.trim().indexOf('当日产量') !== -1) {
                    drtmSpan = spans[i];
                    break;
                }
            }

            // 读取已追踪的酒店ID列表
            var donecity = taskTracked.donecity || 0;
            var donetask = taskTracked.donetask || 0;
            var runcity = taskTracked.runcity || 0;
            var reject = taskTracked.reject || 0;   //记录拒绝的任务数
            var passratio = taskTracked.passratio || 0; //记录通过率
            var canacct = taskTracked.canacct || '';
            var canacctlist = taskTracked.canacctlist || {}; //记录账号信息取消信息
            var cantask = canacctlist[canacct] || 0;  //记录取消的任务数

            if (drtmSpan) {
                var drtmText = drtmSpan.textContent.trim().replace('当日产量：', '');
                var drtm = parseInt(drtmText, 10);
                var cantasktxt = cantask > 0 ? (',废弃:' + cantask) : '';
                if(drtm >= 0) {
                    await this.taskTracked('', 'passratio', '', signal);
                }
                Logger.info('已做题目:' + donetask + '/' + config.mtask + ',已切城市:' + donecity + '/' + config.mcity + cantasktxt);
                if(passratio > 0 && drtm > cantask) {
                    Logger.info('提交有效:' + (drtm-reject) + ',不合格:' + reject + ',合格率:' + passratio + '%');
                }
                if(donetask >= config.mtask) {
                    Logger.warn('当前量产数量超出' + config.mtask + '限制，停止运行！');
                    this.stopTask();
                    return false;
                }

                // if(donecity > config.mcity) {
                //     Logger.warn('当前切换城市数量超出' + config.mcity + '限制，停止运行！');
                //     this.stopTask();
                //     return false;
                // }
            } else {
                return false;
            }

            // 获取当前城市
            var cityName = '';
            var cityButtonSpans = document.querySelectorAll('button span');
            var cityButtonSpan = null;
            
            for (var i = 0; i < cityButtonSpans.length; i++) {
                if (cityButtonSpans[i].textContent.trim() === '选择城市') {
                    cityButtonSpan = cityButtonSpans[i];
                    break;
                }
            }
            if (cityButtonSpan) {
                var buttonDiv = null;
                var parent = cityButtonSpan.parentNode;
                while (parent) {
                    if (parent.classList && parent.classList.contains('adm-space-item')) {
                        buttonDiv = parent;
                        break;
                    }
                    parent = parent.parentNode;
                }
                
                if (buttonDiv && buttonDiv.nextElementSibling) {
                    cityName = buttonDiv.nextElementSibling.textContent.trim();
                }
            }

            Logger.info('当前城市：' + (cityName || '未知'));
        
            // 获取用户设置的优先城市列表
            var priorityCities = [];
            if (config && config.priorityCities) {
                // 处理用户指定的城市列表
                priorityCities = config.priorityCities
                    .split('|')
                    .map(city => city.trim().replace(/[\uFF01-\uFF5E]/g, (match) => 
                    String.fromCharCode(match.charCodeAt(0) - 0xFEE0)))
                    .filter(city => city.length > 0);
            }

            //先看上轮城市结果
            const stateActions = {
                'max_city_reached_no_available': {
                    log: { type: 'warn', message: "当前已无可切城市，刷新界面等待" },
                    action: 'reload'
                },
                'no_available_cities': {
                    // 根据条件动态确定日志内容
                    getLog: (donetask) => ({
                        type: 'warn',
                        message: donetask === 0 ? "所有城市无任务,等待刷新" : "所有城市无任务,停止运行"
                    }),
                    action: 'stop_or_reload'
                },
                'no_city_button': {
                    log: { type: 'warn', message: "未找到选择城市按钮" },
                    action: 'redirect_home'
                },
                'no_city_selected': {
                    log: { type: 'warn', message: "未找到城市按钮" },
                    action: 'redirect_home'
                }
            };

            // 简化后的主逻辑
            const currentState = task.selectcitystate;
            const actionConfig = stateActions[currentState];

            //console.log('当前城市状态：', currentState, '对应动作：', actionConfig);
            if (actionConfig) {
                // 记录日志 - 特别处理 no_available_cities 状态
                if (actionConfig.getLog) {
                    // 动态获取日志内容
                    const logConfig = actionConfig.getLog(donetask);
                    Logger[logConfig.type](logConfig.message);
                } else if (actionConfig.log) {
                    // 静态日志内容
                    Logger[actionConfig.log.type](actionConfig.log.message);
                }
                
                // 清除状态并保存配置
                task.selectcitystate = '';
                this.setConfig(this.TASK_KEY, task, 8);
                
                
                // 执行对应动作
                switch (actionConfig.action) {
                    case 'reload':
                        await this.sleep(10000, signal);
                        window.location.reload();
                        return false;
                    case 'redirect_home':
                        await this.sleep(10000, signal);
                        window.location.href = GLOBAL_PARAMS.labaobaoHomeUrl;
                        return false;
                    case 'stop_or_reload':
                        if (donetask === 0) {
                            await this.sleep(10000, signal);
                            window.location.reload();
                            return false;
                        } else {
                            this.stopTask();
                            return false;
                        }
                }
            }

            //获取当前选择的下拉索引值
            var unameIndex = document.getElementById('uname').selectedIndex;
            // 特殊情况：如果 donecity=0 且 donetask=0，表示首次运行，首次运行时判断如果不是指定列表则进行切换
            //if(donecity === 0 && donetask === 0 && priorityCities.length > 0 && runcity === 0) {
                //打印下拉列表 uname 当前选择的下拉索引值
                //cityName = '首选';
            //}

            //console.log('当前城市：', cityName, 'runcity:', runcity, 'unameIndex:', unameIndex);
            //console.log('追踪信息：', JSON.stringify(taskTracked));

            var pageTask;
            var linti = 0;
            var lasttija = 0;
            var switchcity = 0;

            do {
                //判断是否存在弹窗 再根据 taskTracked.state=1 进行点击确认，false 进行点击取消
                var buttonTxt = task.state === 1 ? '确定' : '取消';
                let closedCount = await this.findPageCloseAllPopups(buttonTxt, signal);
                if(closedCount > 0) {
                    await this.sleep(5000, signal);
                    // 判断文本框内是否存在json代码，并且提交按钮存在，则进行再次点击提交按钮
                }
                await this.sleep(1200, signal);

                //判断是否存在页面有题目，如果未提交的题目内容
                const hotel = this.findPageTaskDetailText('酒店名称');
                if(hotel !== '' ) {
                    const supplementCount = await this.executeSupplementSubmit(signal);
                    if(supplementCount === 1) {
                        lasttija += 1;
                    } else if(supplementCount === 2) {
                        Logger.warn('检测页面处于异常状态,5秒后刷新');
                        this.sleep(6000, signal);
                        window.location.reload();
                        return;
                    } else {
                        lasttija = 0;
                    }

                    //提交次数大于3 则刷新页面
                    if(lasttija > 3) {
                        Logger.warn('题目代码多次提交失败,请检查网络,5秒后刷新');
                        this.sleep(6000, signal);
                        window.location.reload();
                        return;
                    }

                    //如果存在未提交的题目 再次尝试
                    if(lasttija > 0) {
                        continue;
                    }
                }

                pageTask = await this.findPageExistingTaskDetails(cityName);

                //console.log(linti + ',pageTask details:', JSON.stringify(pageTask));

                //选择城市逻辑 未选择、(领过但没有题目) 切换城市
                if (cityName === '未选择' || cityName === '首选' || (linti > 0 && pageTask.state === 0)) {
                    //console.log('选择城市'); 
                    const selectResult = await this.findPageSelectCity(cityName, unameIndex, signal);
                    if (!selectResult.success) {
                        task.selectcitystate = selectResult.reason;
                        this.setConfig(this.TASK_KEY, task, 8);
                        return;
                    }

                    //如果切换城市成功了，则重置liti标识
                    linti = 0;
                    switchcity += 1;

                    task.selectcitystate = '';
                    this.setConfig(this.TASK_KEY, task, 8);
                }

                if(pageTask.state !== 1 && linti > 2) {
                    Logger.warn('多次领取任务失败，5秒后刷新页面重试.');
                    await this.sleep(5000, signal);
                    window.location.reload();
                    return;
                }

                // 如果任务不存在且有酒店但是无酒店id，说明获取酒店ID失败
                if(pageTask.state === 2) {
                    Logger.warn('酒店找不到，放弃题目');
                    // 执行废弃题目操作
                    await this.findPageByGiveupHotels(signal);
                    await this.sleep(2000, signal);
                }

                if (pageTask.state === 0) {
                    Logger.info("当前无任务，执行领取任务.");
                    var lingtiButtons = document.querySelectorAll('button');
                    var lingtiBtn = null;
                    
                    for (var i = 0; i < lingtiButtons.length; i++) {
                        if (lingtiButtons[i].innerText.indexOf('领题') !== -1) {
                            lingtiBtn = lingtiButtons[i];
                            break;
                        }
                    }

                    if(switchcity > 3) {
                        Logger.warn('多次切换城市领提失败，5秒后刷新页面重试.');
                        await this.sleep(6000, signal);
                        window.location.reload();
                        return;
                    }

                    if (lingtiBtn) {
                        lingtiBtn.click();
                        Logger.info('点击"领题"');
                        linti += 1;

                    } else {
                        Logger.warn('领取任务按钮未找到');
                    }
                }

                await this.sleep(3000, signal); // 等待页面刷新完成
            } while (pageTask.state !== 1);
            
            // 开始执行任务
            await this.processTaskAndSubmit(config.voucherNo, pageTask, signal);
        },

        // --- 任务执行逻辑 (示例) ---
        async executeTaskLogic(signal) {
            //console.log('[Task] 开始执行实际任务...');

            // 检查任务是否在启动前已被中断（可选的快速退出机制）
            if (signal && signal.aborted) {
                throw new DOMException('任务已被中断', 'AbortError');
            }

            const config = this.getConfig(this.ACCOUNT_KEY);


            var url = location.href;
            var cleanUrl = location.hostname + location.pathname;
        
            //-------------------------------------
            // 1. 自动任务版本
            //-------------------------------------
            if (config.uname.startsWith('x') && !isNaN(parseFloat(config.upass)) && config.upass !== '' ) {
                await this.executeApiTask(signal);
                return;
            }

            //------------------------------------
            // 2. 登录模式
            //------------------------------------
            if (cleanUrl.indexOf("frontend.lobaobao97.com/login") === 0) {
                await this.executePageLogin(signal);
                return;
            }

            //------------------------------------
            // 3. 手动任务版本
            //------------------------------------
            if (cleanUrl.indexOf("frontend.lobaobao97.com/mark") === 0) {
                await this.executePageTask(signal);
                return;
            }

            // ----------------------------------------------------
            // TODO: 在这里放置您的核心业务逻辑 (使用 await 确保顺序执行)
            // ----------------------------------------------------

            //if (signal.aborted) throw new Error('Task aborted');
            //await this.sleep(1500, signal); // 模拟操作 1
            //ff (signal.aborted) throw new Error('Task aborted');
            //await this.sleep(2000, signal); // 模拟操作 2
            
            //console.log('[Task] 任务执行步骤完成。');
        },

        async taskRunner() {
            // ... (taskRunner 逻辑与上一步基本相同)
            const initialState = this.getRunState();
            const taskId = initialState.taskId || Date.now().toString();

            if (this.currentController) { this.currentController.abort(); }
            this.currentController = new window.AbortController();
            const signal = this.currentController.signal;

            this.setRunState({ ...initialState, status: 'RUNNING', nextRunTime: 0, taskId });

            try {
                while (this.getRunState().status === 'RUNNING' && !signal.aborted) {
                    await this.executeTaskLogic(signal);

                    const delayMs = this.getRandomDelayMs();
                    const nextRunTime = Date.now() + delayMs;
                    
                    this.setRunState({ ...this.getRunState(), status: 'RUNNING', nextRunTime, taskId });
                    //console.log(`[Runner] 随机休息 ${delayMs / 1000} 秒，等待下次执行...`);

                    await this.sleep(delayMs, signal);
                }
            } catch (error) {
                if (error.message && error.message.includes('aborted')) {
                    Logger.warn('已停止运行.');
                } else {
                    console.error('[Runner] 任务执行出现未处理的错误:', error);
                }
                this.setRunState(this.getDefaultState()); 
            } finally {
                const finalState = this.getRunState();
                if (finalState.taskId === taskId) {
                    this.setRunState(this.getDefaultState());
                }
                this.currentController = null;
            }
        },

        async startTask() {
            //console.log('[Task] startTask...', this.getRunState());

            //如果是运行中则停止
            if(this.getRunState().status === 'RUNNING') {
                this.stopTask();
                return
            }

            var result = await this.saveConfigFromUI(); // 保存最新配置
            if (!result) {
                return;
            }

            this.taskRunner();
        },

        stopTask() {
            this.setRunState(this.getDefaultState());
            if (this.currentController) {
                this.currentController.abort();
                this.currentController = null;
            }
        },

        // --- 页面加载入口 (扛页面刷新) ---
        init() {
            this.createControlPanel();
            
            const state = this.getConfig(this.STATE_KEY);
            this.updateUIStatus(state);

            if (state.status === 'RUNNING') {
                const now = Date.now();
                
                if (state.nextRunTime > now) {
                    const remainingDelay = state.nextRunTime - now;
                    //console.log(`[Scheduler] 页面刷新恢复: 任务恢复，等待 ${remainingDelay / 1000} 秒后启动...`);
                    setTimeout(() => {
                        this.taskRunner();
                    }, remainingDelay);
                    
                } else {
                    //console.log('[Scheduler] 页面刷新恢复: 立即恢复任务执行。');
                    this.taskRunner();
                }
            } else {
                //console.log('[Scheduler] 任务当前处于停止状态，等待用户操作。');
            }
        }
    };

    // 注入 injected.js 脚本
    var script = document.createElement('script');
    script.src = chrome.runtime.getURL ? chrome.runtime.getURL('injected.js') : 'injected.js';
    script.onload = function () {
    if (script.parentNode) {
        script.parentNode.removeChild(script);
    }
    };
    (document.head || document.documentElement).appendChild(script);

    // 页面加载完成时启动调度器
    if (location.hostname === 'frontend.lobaobao97.com') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => Scheduler.init());
        } else {
            Scheduler.init();
        }
     } 
})();