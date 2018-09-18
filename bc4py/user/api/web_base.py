import json
from aiohttp import web

# Content-Type
CONTENT_TYPE = 'Content-Type'
CONTENT_TYPE_HTML = {'Content-Type': 'text/html'}
CONTENT_TYPE_JSON = {'Content-Type': 'application/json'}


def content_type_json_check(request):
    if request.content_type != 'application/json':
        raise TypeError('Content-Type is application/json,'
                        ' not {}'.format(request.content_type))
    else:
        return request.json()


def json_res(data):
    return web.Response(
        text=json.dumps(data, indent=4),
        content_type='application/json')


def error_res():
    import traceback
    tb = traceback.format_exc()
    return web.Response(text=str(tb), status=400)
