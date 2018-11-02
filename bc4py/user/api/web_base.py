import json
from aiohttp import web
import logging
import json

# Content-Type
CONTENT_TYPE = 'Content-Type'
CONTENT_TYPE_HTML = {'Content-Type': 'text/html'}
CONTENT_TYPE_JSON = {'Content-Type': 'application/json'}


async def content_type_json_check(request):
    if request.content_type != 'application/json':
        raise TypeError('Content-Type is application/json,'
                        ' not {}'.format(request.content_type))
    else:
        try:
            return await request.json()
        except json.JSONDecodeError:
            # POST method check, but No body found
            body = await request.text()
            logging.error("content_type_json_check() body={}".format(body))


def json_res(data):
    return web.Response(
        text=json.dumps(data, indent=4),
        content_type='application/json')


def error_res():
    import traceback
    tb = traceback.format_exc()
    return web.Response(text=str(tb), status=400)
