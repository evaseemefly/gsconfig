'''
    将 自定义error放置此处
'''


class GeoServerError(Exception):
    '''
        自定义的 GeoServer 的父 exception
    '''
    pass


class LayerError(GeoServerError):

    def __init__(self,title:str, expression=None, message=None):
        self.baseMsg = 'layer已经存在'
        self.title=title
        self.expression = expression
        self.message = message

