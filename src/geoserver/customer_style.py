import requests
from geoserver.catalog import Catalog


def bind_layer_style(cat: Catalog, layer_name: str, style_name: str, coverage_title: str,work_space:str):
    '''

    '''
    if check_style(cat, style_name):
        headers_xml = {'content-type': 'text/xml'}
        json_data = f'''
                    <layer>
                            <defaultStyle>
                                <name>{style_name}</name>
                            </defaultStyle>
                        </layer>
                   '''
        # 'http://localhost:8080/geoserver/rest//workspaces/my_test_2/layers/ceshi_coverage_01'
        # TODO:[*] 20-03-26 注意此部分需要去掉工作区(之前是要包含工作区的)
        # url_style = f'http://localhost:8080/geoserver/rest/workspaces/{work_space}/layers/{coverage_title}'
        url_style = f'http://localhost:8080/geoserver/rest/layers/{coverage_title}'
        response = requests.put(
            url_style,
            auth=('admin', 'geoserver'),
            data=json_data,
            headers=headers_xml)
        print(response)
        pass

    pass


def check_style(cat: Catalog, style_name: str):
    '''
        判断指定工作区下是否包含指定的 style
    '''
    return cat.get_style(style_name)

# class Style:
#     def __init__(self):
