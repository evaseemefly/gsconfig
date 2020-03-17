from support import coverageview_xml
from catalog import Catalog
from layer import CoverageLayer
from xml.etree.ElementTree import TreeBuilder, tostring, XMLParser


def coverage_xml():
    '''
        测试 创建 metadata node
        测试: 成功
    '''
    builder = TreeBuilder()
    dict_coverage = dict(
        coverageview=dict(
            coveragebands=dict(
                coverageband_1=dict(
                    definition='ceshi',
                    index=1,
                    inputcoveragebands=dict(
                        inputcoverageband=dict(
                            coverageName='x_wind_10m'
                        )
                    )
                ),
                coverageband_2=dict(
                    definition='ceshi',
                    index=1
                )
            )
        )
    )
    coverageview_xml(builder, dict_coverage)
    XMLParser()
    msg = tostring(builder.close())
    pass


def create_nc_layer():
    '''
        测试创建 nc layer
    '''
    ws_name: str = 'my_test_2'
    cat: Catalog = Catalog("http://localhost:8082/geoserver/rest", username="admin", password="geoserver")
    layer=CoverageLayer(cat, 'ceshi_name', 'ceshi_native_name', 'ceshi_tile', 'ceshi_native_coveragename')
    # layer.message()


    pass


def main():
    # coverage_xml()
    create_nc_layer()


if __name__ == '__main__':
    main()
