import requests
from requests.exceptions import *

from py12306.helpers.func import *
from requests_html import HTMLSession, HTMLResponse

requests.packages.urllib3.disable_warnings()


class Request(HTMLSession):
    """
    请求处理类
    """

    def __init__(self):
        super().__init__()
        # 注册 _handle_response 到 response hooks,这样每次响应都会 expand_class,
        # response.json() 才会返回 Dict 而不是普通 dict
        self.hooks['response'].append(self._handle_response)

    # session = {}
    def save_to_file(self, url, path):
        response = self.get(url, stream=True)
        with open(path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return response

    @staticmethod
    def _handle_response(response, **kwargs) -> HTMLResponse:
        """
        扩充 response
        :param response:
        :param kwargs:
        :return:
        """
        # requests-html 的 HTMLSession 没有 _handle_response 方法(叫 response_hook)。
        # 原代码调用 HTMLSession._handle_response 一直 AttributeError,导致这条路径从未生效。
        # 这里直接做 expand_class,无需转换 response 类型,只需在 response 上设置 json 方法即可。
        if response is not None:
            expand_class(response, 'json', Request.json)
        return response

    def add_response_hook(self, hook):
        hooks = self.hooks['response']
        if not isinstance(hooks, list):
            hooks = [hooks]
        hooks.append(hook)
        self.hooks['response'] = hooks
        return self

    def json(self, default={}):
        """
        重写 json 方法，拦截错误
        :return:
        """
        from py12306.app import Dict
        try:
            result = self.old_json()
            return Dict(result)
        except Exception:
            return Dict(default)

    def request(self, *args, **kwargs):  # 拦截所有错误
        try:
            if not 'timeout' in kwargs:
                from py12306.config import Config
                kwargs['timeout'] = Config().TIME_OUT_OF_REQUEST
            response = super().request(*args, **kwargs)
            return response
        except RequestException as e:
            from py12306.log.common_log import CommonLog
            if e.response:
                response = e.response
            else:
                response = HTMLResponse(HTMLSession)
                # response.status_code = 500
                expand_class(response, 'json', Request.json)
            response.reason = response.reason if response.reason else CommonLog.MESSAGE_RESPONSE_EMPTY_ERROR
            return response

    def cdn_request(self, url: str, cdn=None, method='GET', **kwargs):
        from py12306.helpers.api import HOST_URL_OF_12306
        from py12306.helpers.cdn import Cdn
        if not cdn: cdn = Cdn.get_cdn()
        url = url.replace(HOST_URL_OF_12306, cdn)

        return self.request(method, url, headers={'Host': HOST_URL_OF_12306}, verify=False, **kwargs)

    def dump_cookies(self):
        cookies = []
        for _, item in self.cookies._cookies.items():
            for _, urls in item.items():
                for _, cookie in urls.items():
                    from http.cookiejar import Cookie
                    assert isinstance(cookie, Cookie)
                    if cookie.domain:
                        cookies.append({
                            'name': cookie.name,
                            'value': cookie.value,
                            'url': 'https://' + cookie.domain + cookie.path,
                        })
        return cookies
