# 接口参数
productId: 236
username: xc4584
password: 648549
接口域名: 3.112.30.233:8000


# 接口说明
## 登录

http://域名/api/user/apiLogin?username=账户&password=密码

### 成功返回

```json
{"code":200,"msg":"","result":{"token":"TOKEN"}}
```


## 取号

http://域名/api/phone/getPhone?productId=${productId}&username=${username}&token=${token}

token取登录接口返回的token

### 成功返回

```json
{"code":200,"msg":"成功","result":{"phones":"18888888888"}}
```

### 失败返回

```json
{"code":500,"msg":"卡余量不足","result":""}
```

如果返回失败需要反复取号

## 取码
取码时间设置三分钟

http://域名/api/phone/getCode?productId=${productId}&username=${username}&token=${token}&phone=${phone}

### 成功返回

```json
{"code":200,"msg":"","result":{"code":"622243","status":1}}
```

### 失败返回

```json
{"code":500,"msg":"卡余量不足","result":""}
```

如果返回失败需要反复取号,反馈卡量不足循环获取，每次取码后需要加0.1秒延迟
