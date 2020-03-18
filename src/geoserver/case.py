from support import coverageview_meta_info, coverageview_xml
from catalog import Catalog
from layer import CoverageLayer
from xml.etree.ElementTree import TreeBuilder, tostring, XMLParser
# 新加入的mid model
from mid_model import CoverageDimensionMidModel


def coverage_meta_xml():
    builder = TreeBuilder()
    dict_meta = dict(
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
    coverageview_meta_info(builder, dict_meta)
    return builder


def coverage_xml():
    '''
        测试 创建 metadata node
        测试: 成功
    '''

    dict_meta = dict(
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
    dict_coverage = dict(
        name='ceshi_coverage_01',
        nativeName='ceshi_coverage_01',
        namespace=dict(
            name='my_test_2',
            atom='my_test_2'
        ),
        title='ceshi_coverage_01',
        description='Generated from NetCDF',
        nativeCoverageName='ceshi_coverage_01',
        # metadata=dict_meta,
        metadata=[
            dict(
                key='COVERAGE_VIEW',
                name='entry',
                tag='',
                val=dict_meta
            ),
            dict(
                key='cachingEnabled',
                name='entry',
                tag='',
                val='false'
            ),
            dict(
                key='dirName',
                name='entry',
                tag='',
                val='nmefc_wind_dir_xy_view_nmefc_wind'
            )
        ],
        store='',
        dimensions=dict(
            coverageDimension_1=CoverageDimensionMidModel('x_wind_10m', 'GridSampleDimension[-Infinity,Infinity]',
                                                          ['-inf', 'inf'], 'REAL_32BITS'),
            coverageDimension_2=CoverageDimensionMidModel('y_wind_10m', 'GridSampleDimension[-Infinity,Infinity]',
                                                          ['-inf', 'inf'], 'REAL_32BITS'),

        )
        # dimensions=[
        #     dimension=1,
        #     ceshi='123',
        #     # coverageDimension=CoverageDimensionMidModel('x_wind_10m','GridSampleDimension[-Infinity,Infinity]',['-inf','inf'],'REAL_32BITS')
        # ]

    )
    # builder = TreeBuilder()
    builder = coverageview_xml(dict_coverage)
    # coverageview_meta_info(builder, dict_meta)
    return builder

    pass


def info_xml():
    builder = TreeBuilder()
    builder.start('root', dict())
    builder.data('ceshi')
    builder.start('child', dict())
    builder.data('child_1_data')
    builder.end('child')
    builder.end('root')
    return builder
    # msg= tostring(builder.close(),encoding='utf-8',method='xml')
    # print(msg)
    pass


def create_nc_layer():
    '''
        测试创建 nc layer
    '''
    ws_name: str = 'my_test_2'
    cat: Catalog = Catalog("http://localhost:8082/geoserver/rest", username="admin", password="geoserver")
    layer = CoverageLayer(cat, 'ceshi_name', 'ceshi_native_name', 'ceshi_tile', 'ceshi_native_coveragename')
    layer.message()

    pass


def main():
    builder = coverage_xml()
    # create_nc_layer()
    # builder=info_xml()
    # 测试可行
    # builder=coverage_meta_xml()
    msg = tostring(builder.close(), encoding='utf-8', method='xml')
    print(msg)
    pass


if __name__ == '__main__':
    main()
