import requests
from geoserver.catalog import Catalog

# class Style:
#     def __init__(self):
from geoserver.catalog import Catalog
import os
from customer_base import BaseCatalog

# 样式文件默认存储的路径
SLD_SRC = r'D:\GeoServer 2.13.0\data_dir\styles'


def bind_layer_style(cat: Catalog, layer_name: str, style_name: str, coverage_title: str, work_space: str):
    '''
        将 layer 绑定指定的 style ,暂时不放在 class中
        TODO:[*] 20-03-31 此部分与 cwb 的 LayerStyle 需要整合，暂时不再修改
    @param cat:
    @param layer_name:
    @param style_name:
    @param coverage_title:
    @param work_space:
    @return:
    '''
    is_ok = False
    if check_style(cat, style_name, work_space) is not None:
        headers_xml = {'content-type': 'text/xml'}
        json_data = f'''
                    <layer>
                            <defaultStyle>
                                <name>{style_name}</name>
                            </defaultStyle>
                        </layer>
                   '''
        # 'http://localhost:8080/geoserver/rest//workspaces/my_test_2/layers/ceshi_coverage_01'
        # TODO:[-] 20-03-26 注意此部分需要去掉工作区(之前是要包含工作区的),03-30 更新，修改版本为 2.15.1
        url_style = f'{cat.service_url}/workspaces/{work_space}/layers/{coverage_title}'
        response = requests.put(
            url_style,
            auth=(cat.username, cat.password),
            data=json_data,
            headers=headers_xml)
        pass
        # print(response)


def check_style(cat: Catalog, style_name: str, work_space_name: str):
    '''
        判断指定工作区下是否包含指定的 style
    '''
    # cat.get_styles()
    # TODO:[-] 20-03-30 注意需要加入 ws，否则会报错
    temp_style = cat.get_style(style_name, work_space_name)
    return temp_style


class BaseStyle(BaseCatalog):
    '''
        20-03-31 + 新加入的 继承自 BaseCatalog的 父类样式 ，需要由具体实现 style 继承
    '''

    def __init__(self, cat: Catalog, work_space_name: str):
        super().__init__(cat, work_space_name)
        # self.cat = cat
        # self.work_space_name = work_space_name

    def check_style(self, style_name: str):
        '''
            检查 指定 -> ws -> style 是否存在
        @param style_name: 样式 名称
        @return:
        '''
        temp_style = self.cat.get_style(style_name, self.work_space)
        return temp_style


class LayerStyle(BaseStyle):
    def __init__(self, catalog: Catalog, work_space: str, layer_name: str):
        '''
        初始化LayerStyle类
        :param catalog: 当前catalog对象
        :param work_space: 需要绑定Layer的工作区
        :param layer_name: 需要绑定Style的Layer
        '''
        super().__init__(catalog, work_space)
        # self.catalog = catalog
        # self.work_space = work_space
        self.layer_name = layer_name

    def has_the_style(self, layer, style_name: str):
        '''
        判断指定图层是否包含指定样式
        :param layer: 需要判断的图层
        :param style_name: 需要判断样式名
        :return: 如果包含指定图层返回True，没有指定图层返回False
        '''
        if (layer.default_style.name == style_name):
            return True
        for s in layer.styles:
            if (s.name == style_name):
                return True
        return False

    def create_style(self, style_name: str, sld_name: str):
        '''
        为指定图层创建默认样式
        :param style_name: 样式名
        :param sld_name: 样式文件名称
        :return: 如果创建图层成功，则返回Layer对象，如果创建失败返回None
        '''
        for layer in self.catalog.get_layers():
            layer_name = self.work_space + ':' + self.layer_name
            if (layer.name == layer_name):
                if (self.has_the_style(layer, style_name)):  # 如果图层已经绑定了Style，只需要设定default_style
                    if (layer.default_style.name != style_name):
                        layer.default_style = style_name
                        self.catalog.save(layer)
                        return layer
                else:  # 如果图层没有绑定Style，需要读取sld文件创建并绑定Style
                    with open(sld_name) as f:
                        self.catalog.create_style(style_name, f.read(), overwrite=True)
                        layer.default_style = style_name
                        self.catalog.save(layer)
                        return layer
        return None

    def bind_layer_style(self, style_name: str, coverage_title: str):
        '''
            TODO:[-] 20-03-31 + 添加至 layer_style中
        @param style_name:
        @param coverage_title:
        @return:
        '''
        is_ok = False
        if self.check_style(style_name) is not None:
            headers_xml = {'content-type': 'text/xml'}
            json_data = f'''
                            <layer>
                                    <defaultStyle>
                                        <name>{style_name}</name>
                                    </defaultStyle>
                                </layer>
                           '''
            # 'http://localhost:8080/geoserver/rest//workspaces/my_test_2/layers/ceshi_coverage_01'
            # TODO:[-] 20-03-26 注意此部分需要去掉工作区(之前是要包含工作区的),03-30 更新，修改版本为 2.15.1
            url_style = f'{self.cat.service_url}/workspaces/{self.work_space.name}/layers/{coverage_title}'
            response = requests.put(
                url_style,
                auth=(self.cat.username, self.cat.password),
                data=json_data,
                headers=headers_xml)
            if response.status_code in [200, 201]:
                is_ok = True
        return is_ok


def main():
    catalog = Catalog("http://localhost:8082/geoserver/rest", "admin", "geoserver")
    layer_style = LayerStyle(catalog, 'cite', 'netcdf_wind')
    sld_name = os.path.join(SLD_SRC, 'nmefc_wind_vect.sld')
    layer_style.create_style('nmefc_wind_vect', sld_name)
    pass


if __name__ == '__main__':
    main()
