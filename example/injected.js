(function () {
  const targetSubstring = 'getHotelRoomListInland';

  const base64Encode = (obj) => {
    const jsonStr = JSON.stringify(obj);
    const utf8Bytes = new TextEncoder().encode(jsonStr);
    const binaryStr = Array.from(utf8Bytes).map(byte => String.fromCharCode(byte)).join('');
    return btoa(binaryStr);
  };

  // 用"g 开头，隔一个字母补充"的方式把 key 补到16字节
  function fixKey16(key) {
    if (!key) key = '';
    if (key.length > 16) return key.slice(0, 16);

    const filler = [];
    let fillerChar = 'g'.charCodeAt(0);
    for (let i = 0; i < 16 - key.length; i++) {
      filler.push(String.fromCharCode(fillerChar));
      fillerChar += 2; // 隔一个字母，例如 g(103), i(105), k(107), ...
      if (fillerChar > 'z'.charCodeAt(0)) fillerChar = 'a'.charCodeAt(0); // 超过z就从a开始循环
    }
    return key + filler.join('');
  }

  // 存储管理
  var storage = {
    safeGetItem: function(key) {
      try {
        var item = localStorage.getItem(key);
        if (!item) {
          return null;
        }
        
        try {
          // 尝试解析为JSON对象，检查是否有过期时间
          var data = JSON.parse(item);
          if (data && typeof data === 'object' && data.expire !== undefined) {
            // 检查是否过期
            if (new Date().getTime() > data.expire) {
              // 过期则删除并返回null
              localStorage.removeItem(key);
              return null;
            }
            // 未过期则返回值
            return data.value;
          }
        } catch (e) {
          // 解析失败说明是普通字符串，直接返回
        }
        
        // 普通字符串值
        return item;
      } catch (e) {
        Logger.error('读取存储失败: ' + e.message);
        return null;
      }
    },
    
    safeSetItem: function(key, value, expireHours) {
      try {
        if (expireHours === undefined || expireHours === null || expireHours === 0) {
          // 永不过期
          localStorage.setItem(key, value);
        } else {
          // 设置过期时间（单位：小时）
          var expireTime = new Date().getTime() + (expireHours * 60 * 60 * 1000);
          var data = {
            value: value,
            expire: expireTime
          };
          localStorage.setItem(key, JSON.stringify(data));
        }
        return true;
      } catch (e) {
        Logger.error('写入存储失败: ' + e.message);
        return false;
      }
    },
    
    safeParse: function(key) {
      try {
        var item = this.safeGetItem(key);
        return item ? JSON.parse(item) : null;
      } catch (e) {
        Logger.error('解析存储数据失败: ' + e.message);
        return null;
      }
    }
  };

  const encrypt = async (obj, key) => {
    const jsonStr = JSON.stringify(obj);
    const encoder = new TextEncoder();
    const data = encoder.encode(jsonStr);

    const fixedKey = fixKey16(key);
    const keyRaw = encoder.encode(fixedKey); // 16字节密钥

    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      keyRaw,
      { name: 'AES-CBC' },
      false,
      ['encrypt']
    );

    const iv = crypto.getRandomValues(new Uint8Array(16));
    const encrypted = await crypto.subtle.encrypt({ name: 'AES-CBC', iv }, cryptoKey, data);

    const resultBytes = new Uint8Array(iv.byteLength + encrypted.byteLength);
    resultBytes.set(iv, 0);
    resultBytes.set(new Uint8Array(encrypted), iv.byteLength);

    const binaryStr = Array.from(resultBytes).map(byte => String.fromCharCode(byte)).join('');
    return btoa(binaryStr);
  };

  const checkPageStatus = () => {
    // 检查是否存在特定的404页面结构
    const bgDiv = document.querySelector('div.bg');
    const has404Structure = bgDiv && 
      bgDiv.querySelector('div.tower') && 
      bgDiv.querySelector('div.beam') && 
      bgDiv.querySelectorAll('div[class^="star"]').length >= 4;
    
    if (has404Structure) {
      console.log('[Page Status] 404 - Page not found');
      return true;
    }
    
    return false;
  };

  // 提取酒店ID的公共方法
  const extractHotelId = () => {
    const params = new URLSearchParams(window.location.search);
    let hotelId = params.get('hotelId');
    
    if (!hotelId) {
      const pathParts = window.location.pathname.split('/');
      const lastPart = pathParts[pathParts.length - 1];
      if (lastPart && lastPart.endsWith('.html')) {
        const extractedId = lastPart.replace('.html', '');
        // 加强验证：确保提取的ID是数字
        if (/^\d+$/.test(extractedId)) {
          hotelId = extractedId;
        }
      }
    }
    
    return hotelId;
  };

// 提取入住时间的公共方法
  const extractCheckin = () => {
    const params = new URLSearchParams(window.location.search);
    let checkin = params.get('checkIn');

    if (!checkin) {
      checkin = ''; // 直接返回空字符串
    }
    return checkin;
  };

  // 处理并发送酒店数据的公共方法
  const processAndSendData = async (data) => {
    const hotelId = extractHotelId();
    const checkin = extractCheckin();
    if (window.opener != null && hotelId) {
    //if (hotelId) {
      try {
        const hid = await base64Encode(hotelId);
        const ext = await encrypt(data, hotelId);

        // 如果 checkin 不为空则加密，否则使用空字符串
        const checkinValue = checkin ? await base64Encode(checkin) : '';
        const response = await fetch('https://www.jpzz.top/api/lobaobao/temporary', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ hid, ext, checkin: checkinValue }),
        });
        
        const json = await response.json();
        if(json.data === 1) {
          var injectedData = storage.safeParse('injected') || {};
          var total = injectedData.total || 0;
          var today = new Date().setHours(0, 0, 0, 0);
          var todayTotal = injectedData.todayTotal || 0;
          var todayDate = injectedData.todayDate || 0;
          var todyOrder1 = injectedData.todyOrder1 || 0;
          var todyOrder2 = injectedData.todyOrder2 || 0;
          var todayOrderNum = injectedData.todayOrderNum || 0;
          var todayCancel = injectedData.todayCancel || 0;
          var todayCancelNum = injectedData.todayCancelNum || 0;
          //获取今天时间如果不等于今天 则重置
          if(today !== todayDate) {
            todayTotal = 0;
            todayDate = today;
            todayOrderNum = 0;
            todyOrder1 = total === 0 ? 5 : (Math.floor(Math.random() * (30 - 20 + 1)) + 20);
            todyOrder2 = total === 0 ? (Math.floor(Math.random() * 11) + 90) : (Math.floor(Math.random() * 21) + 100);
            todayCancel = 0;
            todayCancelNum = 0;
          }

          //总数和今天数量都加1
          injectedData.total = total + 1;
          injectedData.todayTotal = todayTotal + 1;
          injectedData.todayDate = todayDate;
          injectedData.todyOrder1 = todyOrder1;
          injectedData.todyOrder2 = todyOrder2;
          injectedData.todayOrderNum = todayOrderNum;
          storage.safeSetItem('injected', JSON.stringify(injectedData), 0);

          //判断是否操作下单
          // 在条件判断内部添加重试逻辑
          //if((todayTotal > todyOrder1 && todayOrderNum === 0) || (todayTotal > todyOrder2 && todayOrderNum === 1)) {
          if(todayTotal > todyOrder1 && todayOrderNum === 0) {
            //if(today > 0) {
            let retryCount = 0;
            const maxRetries = 10;
            const retryInterval = 1000; // 1000ms间隔
            
            const tryClickBookingButton = () => {
                const buttons = document.querySelectorAll('button.tripui-online-btn');
                for (let button of buttons) {
                    const span = button.querySelector('span.tripui-online-btn-content-children');
                    if (span && span.textContent.replace(/\s+/g, '').trim() === '预订') {
                        // 找到预订按钮，执行点击操作 并记录
                        injectedData.todayOrderNum = todayOrderNum + 1;
                        injectedData.todayCancelNum = todayTotal + 3;
                        //storage.safeSetItem('injected', JSON.stringify(injectedData), 0);
                        //button.click(); 不下单
                        return true;
                    }
                }
                
                if (retryCount < maxRetries) {
                    retryCount++;
                    setTimeout(tryClickBookingButton, retryInterval);
                }
                return false;
            };
            
            tryClickBookingButton();
          } else if(todayOrderNum > 0 && todayTotal > todayCancelNum && todayCancel < 3) {
            // 找到预订按钮，执行点击操作 并记录
            injectedData.todayCancel = todayCancel + 1;
            storage.safeSetItem('injected', JSON.stringify(injectedData), 0);
            //已经下单过了，过了三单进入取消订单
            window.location.href = 'https://my.ctrip.com';
          } else {
            window.close();
          }
        } else {
          window.close();
        }
      } catch (err) {
        console.error('[数据分析] 异常:', err);
      }
    }
  };

  // 页面加载时检查URL参数，符合条件则启动20秒自动关闭计时器
  const isOpenedByScript = window.opener != null;
  if (isOpenedByScript) {
    console.log('[close]20s');
    setTimeout(() => {
      window.close();
    }, 20000); // 20秒后自动关闭页面

    setTimeout(() => {
      //404页面
      if(checkPageStatus()) {
        var data = {"data":{"htlSpiderActionErrorCode":404},"ResponseStatus":{"Timestamp":"/Date(1755525558131+0800)/","Ack":"Success","Errors":[],"Build":"","Version":"1.0.0","Extension":[{"Id":"CLOGGING_TRACE_ID","Value":""},{"Id":"TraceLogId","Value":"100025527-0a2d8381-487645-3651272"},{"Id":"XRequestId","Value":"e4368e40-df8d-4b57-94e3-aca98e0b7c1b"},{"Id":"RootMessageId","Value":"100025527-0a2d8381-487645-3651275"}]}};
        processAndSendData(data);
      }
    }, 4000);
    
  }

  // 拦截 fetch
  const originalFetch = window.fetch;
  window.fetch = new Proxy(originalFetch, {
    apply(target, thisArg, args) {
      const input = args[0];
      const url = typeof input === 'string' ? input : input.url;

      return target.apply(thisArg, args).then(async (response) => {
        const cloned = response.clone();

        if (url && url.includes(targetSubstring)) {
          try {
            const contentType = cloned.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
              const data = await cloned.json();
              await processAndSendData(data);
            }
          } catch (e) {
            console.warn('[Fetch 响应解析失败]', e);
          }
        }
        return response;
      });
    }
  });

  // 拦截 XHR
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, async, user, password) {
    this._interceptUrl = url;
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function (body) {
    if (this._interceptUrl && this._interceptUrl.includes(targetSubstring)) {
      this.addEventListener('load', async () => {
        try {
          const contentType = this.getResponseHeader('content-type') || '';
          if (contentType.includes('application/json')) {
            const data = JSON.parse(this.responseText);
            await processAndSendData(data);
          }
        } catch (e) {
          console.warn('[XHR 响应解析失败]', e);
        }
      });
    }
    return originalSend.apply(this, arguments);
  };

  // 模拟用户输入函数
  function setNativeValue(element, value) {
    const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
    const prototype = Object.getPrototypeOf(element);
    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;

    if (valueSetter && valueSetter !== prototypeValueSetter) {
        prototypeValueSetter.call(element, value);
    } else {
        valueSetter.call(element, value);
    }

    // 触发 React/Vue 感知的输入事件
    element.dispatchEvent(new Event('input', { bubbles: true }));
  }

  const randomNames = ['张伟', '王芳', '李娜', '刘强', '陈敏', '杨洋', '赵磊', '孙丽', '周杰', '吴倩'];

  if (window.location.hostname.includes('hotels.ctrip.com') && window.opener != null) {
    if(window.location.href.indexOf('booknew') !== -1) {
       // 等待加载完成，获取文本框和最后一步后获取按钮，如果文本框没有值则填写徐行 ,再进行点击 最后一步按钮
      let retryCount = 0;
      const maxRetries = 19;
      const retryInterval = 1000; // 1000ms间隔
      const upcount = 0;

      const tryProcessBookingPage = () => {
        try {
            // 改进的查找住客姓名输入框方法
            const findNameInput = () => {
                // 按优先级顺序尝试不同的选择器
                const selectors = [
                    '.full-name-input .input-wrapper input[placeholder="每间只需填1人"]',
                    '.fullName.input .input-wrapper input[placeholder="每间只需填1人"]',
                    'div.full-name-input div.fullName.input div.input-wrapper input[placeholder="每间只需填1人"]',
                    'input[placeholder="每间只需填1人"]'
                ];
                
                for (let selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    // 优先选择可见的、已渲染的元素
                    for (let element of elements) {
                        if (element.offsetParent !== null && !element.disabled) {
                            return element;
                        }
                    }
                }
                return null;
            };
            // 查找住客姓名输入框
            const nameInput = findNameInput();
            // 获取手机号          
            const phone = document.querySelector('input[id="phoneNumber"]') ? document.querySelector('input[id="phoneNumber"]').value.trim() : '';

            // 只有当手机号不为空时才发起请求
            if (phone === '123456789') {
              // 同步方式请求服务端链接
              const xhr = new XMLHttpRequest();
              xhr.open('GET', 'https://www.jpzz.top/api/lobaobao/place?id=' + phone + '&type=1', false); // 同步请求
              xhr.send();

              if (xhr.status === 200) {
                const count = parseInt(xhr.responseText);
                if (upcount === 0 && count > 1) {
                  window.close();
                  return; // 不继续执行后面的代码
                }

                if(upcount === 0) {
                  upcount++;
                }
              }
            }
            
            // 查找最后一步按钮
            const lastStepButtonSpan = document.querySelector('button.tripui-online-btn span.text');
            
            if (nameInput && lastStepButtonSpan && lastStepButtonSpan.textContent.replace(/\s+/g, '').trim() === '最后一步') {
                // 如果文本框没有值则填写
                if (!nameInput.value || nameInput.value.trim() === '') {
                  // 在setTimeout中添加随机延迟
                  setTimeout(() => {
                      try {
                          if (nameInput.offsetWidth === 0 || nameInput.offsetHeight === 0) {
                              console.warn('输入框不可见');
                              return;
                          }

                          nameInput.scrollIntoView({ behavior: 'smooth', block: 'center' });

                          setTimeout(() => {
                              nameInput.focus();
                              const randomName = randomNames[Math.floor(Math.random() * randomNames.length)];
                              //使用 setNativeValue 模拟真实用户输入
                              setNativeValue(nameInput, randomName);
                              // 模拟 blur 事件（部分站点依赖它进行验证）
                              setTimeout(() => {
                                  nameInput.dispatchEvent(new Event('blur', { bubbles: true }));
                              }, 100);
                          }, 300);
                      } catch (inputError) {
                          console.error('输入操作失败:', inputError);
                      }
                  }, 1000);
                }
                // 点击最后一步按钮
                const lastStepButton = lastStepButtonSpan.closest('button.tripui-online-btn');
                if (lastStepButton) {
                    lastStepButton.click();
                }
            }
            
            if (retryCount < maxRetries) {
                retryCount++;
                setTimeout(tryProcessBookingPage, retryInterval);
            } else {
                console.log('未能找到预订页面的必要元素，超过最大重试次数');
            }
            return false;
        } catch (error) {
            console.error('处理出错:', error);
            if (retryCount < maxRetries) {
                retryCount++;
                setTimeout(tryProcessBookingPage, retryInterval);
            }
            return false;
        }
      };
      tryProcessBookingPage();
      
    } else if(window.location.href.indexOf('ctorderdetail') !== -1) {
      setTimeout(() => {
          try {
              // 查找取消原因的单选按钮
              const radioItems = document.querySelectorAll('.radio-item');
              
              // 选择第一个选项"出行计划有变"
              if (radioItems.length > 0) {
                  const firstRadioItem = radioItems[0];
                  firstRadioItem.click();
              }
              
              // 等待一下确保选项被选中
              setTimeout(() => {
                  // 查找提交按钮
                  const submitButton = document.querySelector('.cancel-btn button');

                  //如果进入取消页面，直接增加取消次数 下次不再进入
                  var injectedData = storage.safeParse('injected') || {};
                  injectedData.todayCancel = (injectedData.todayCancel || 0) + 3; 
                  storage.safeSetItem('injected', JSON.stringify(injectedData), 0);

                  if (submitButton) {
                      // 检查按钮是否可用（没有disabled类）
                      if (!submitButton.classList.contains('h-od-online-btn-solid-primary-disabled')) {
                          submitButton.click();
                      } else {
                      }
                  } else {
                    window.close();
                  }
              }, 500);
              
          } catch (error) {
              console.error('处理取消订单页面出错: ' + error.message);
          }
      }, 2000); // 等待2秒确保页面完全加载
    } else {
      // 立即执行滚动，不等待页面加载完成
      setTimeout(function() {
        // 模拟用户滚动行为
        let currentPos = 0;
        const scrollStep = 40;
        const maxScroll = 800;
        const scrollInterval = setInterval(() => {
          currentPos += scrollStep;
          window.scrollBy(0, scrollStep);
          
          // 滚动到指定位置后停止
          if (currentPos >= maxScroll) {
            clearInterval(scrollInterval);
          }
        }, 120);
      }, 1000); // 延迟1秒执行，给页面基本渲染时间
    }
  }

  if (window.location.href.indexOf('my.ctrip.com') !== -1 && window.opener != null) {
    
    // 等待页面加载完成后提取订单信息
    setTimeout(() => {
      const orderList = [];
      const orderElements = document.querySelectorAll('.order-list li.order-list_flight');
      
      orderElements.forEach((orderElement, index) => {
          try {
              // 提取酒店名称
              const hotelNameElement = orderElement.querySelector('h2');
              const hotelName = hotelNameElement ? hotelNameElement.textContent.trim() : '';
              
              // 提提取订单状态
              const statusElement = orderElement.querySelector('.order-status, .order-status-succes');
              const status = statusElement ? statusElement.textContent.trim() : '';
              
              // 提取所有订单信息元素
              const infoElements = orderElement.querySelectorAll('p.order-info');
              
              // 提取预订日期信息（第二个 p.order-info 元素）
              const dateInfo = infoElements.length >= 2 ? infoElements[1].textContent.trim() : '';
              
              // 提取价格信息
              const priceElement = orderElement.querySelector('.order-blod-price');
              const price = priceElement ? priceElement.textContent.trim() : '';
              
              // 提取房间信息（第三个 p.order-info 元素）
              const roomInfo = infoElements.length >= 3 ? infoElements[2].textContent.trim() : '';
              
              // 提取取消链接
              const cancelLinkElement = orderElement.querySelector('.order-ft a.btn02');
              const cancelLink = cancelLinkElement ? cancelLinkElement.href : '';
              
              // 组装订单对象
              const order = {
                  hotelName,
                  status,
                  dateInfo,
                  price,
                  roomInfo,
                  cancelLink
              };
              
              orderList.push(order);
              
              // 如果有待支付订单且存在取消链接，则导航到取消页面
              if (cancelLink) {
                  //console.log(`发现待支付订单，正在导航到取消页面: ${cancelLink}`);
                  // 可以选择立即打开或者稍后处理
                  // window.open(cancelLink, '_blank');
              }
          } catch (error) {
              console.error('解析订单信息出错:', error);
          }
      });
      
      // 输出订单信息到控制台
      console.log('提取到的订单信息:', JSON.stringify(orderList));
      
      // 查找第一个待支付订单并导航到取消页面
      const pendingOrder = orderList.find(order => order.cancelLink);
      if (pendingOrder) {
          console.log('找到待支付订单，准备跳转到取消页面...');
          // 添加延时避免阻塞
          setTimeout(() => {
              window.location.href = pendingOrder.cancelLink;
          }, 3000);
      }
      
    }, 2000); // 等待2秒确保页面完全加载
  }

  if (window.location.hostname.includes('secure.ctrip.com') && window.opener != null) {
    //过2秒关闭
    setTimeout(() => {
      window.close();
    }, 2000);
  }

})();