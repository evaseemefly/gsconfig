import os
import requests

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
            # TODO:[-] + 加入的部分
            name='ceshi_coverage_01',
            envelopeCompositionType='INTERSECTION',
            selectedResolution='',
            selectedResolutionIndex='-1',
            # 之前的
            coveragebands=dict(
                coverageband_1=dict(
                    definition='x_wind_10m',
                    index=0,
                    inputcoveragebands=dict(
                        inputcoverageband=dict(
                            coverageName='x_wind_10m'
                        )
                    )
                ),
                coverageband_2=dict(
                    definition='y_wind_10m',
                    index=1,
                    inputcoveragebands=dict(
                        inputcoverageband=dict(
                            coverageName='y_wind_10m'
                        )
                    )
                ),
            )
        )
    )
    dict_coverage = dict(
        name='ceshi_coverage_01',
        nativeName='ceshi_coverage_01',
        namespace=dict(
            name='my_test_2',
            atom='ceshi'
        ),
        title='ceshi_coverage_01',
        description='Generated from NetCDF',
        nativeCoverageName='ceshi_coverage_01',
        # TODO:[-] + 20-03-19 新增部分
        enabled='true',
        nativeFormat='NetCDF',
        requestSRS=dict(string='EPSG:4326'),
        responseSRS=dict(string='EPSG:4326'),
        defaultInterpolationMethod='nearest neighbor',
        # 之前的
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
        # TODO:[-] + 20-03-19 修改的 store
        store=dict(
            classname='coverageStore',
            name='my_test_2:nmefc_2016072112_opdr'
        ),
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


def create_nc_coverage():
    builder = coverage_xml()
    msg = tostring(builder.close(), encoding='utf-8', method='xml')
    # 测试一下提交
    coverage_title = 'ceshi_coverage_01'
    store_name = 'nmefc_wind'
    coveragestore = 'nmefc_wind'
    WORK_SPACE = 'ceshi'
    # TODO:此种方式提交的有多路band

    headers_xml = {'content-type': 'text/xml'}
    # TODO:[-] 20-03-19 提交时出现一个错误
    # 错误1: 已解决
    # requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=8082): Max retries exceeded with url: /geoserver/rest/workspaces/ceshi/coveragestores/nmefc_wind/coverages (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x122c3f3d0>: Failed to establish a new connection: [Errno 61] Connection refused'))
    # 接口mac是8080

    # 错误2: org.springframework.web.util.NestedServletException: Request processing failed; nested exception is java.lang.NullPointerException
    # 加入测试的数据,可行，应该还是拼接数据的问题
    msg = f'''
            <coverage>
  <name>ceshi_coverage_01</name>
  <nativeName>ceshi_coverage_01</nativeName>
  <namespace>
    <name>my_test_2</name>
    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/namespaces/my_test_2.xml" type="application/xml"/>
  </namespace>
  <title>ceshi_coverage_01</title>
  <description>Generated from NetCDF</description>
  <keywords>
    <string>ceshi_coverage_01</string>
    <string>WCS</string>
    <string>NetCDF</string>
  </keywords>
  <nativeCRS>GEOGCS["WGS 84", DATUM["World Geodetic System 1984", SPHEROID["WGS 84", 6378137.0, 298.257223563, AUTHORITY["EPSG","7030"]], AUTHORITY["EPSG","6326"]], PRIMEM["Greenwich", 0.0, AUTHORITY["EPSG","8901"]], UNIT["degree", 0.017453292519943295], AXIS["Geodetic longitude", EAST], AXIS["Geodetic latitude", NORTH], AUTHORITY["EPSG","4326"]]</nativeCRS>
  <srs>EPSG:4326</srs>
  <projectionPolicy>REPROJECT_TO_DECLARED</projectionPolicy>
  <enabled>true</enabled>
  <metadata>
    <entry key="COVERAGE_VIEW">
      <coverageView>
        <coverageBands>
          <coverageBand>
            <inputCoverageBands class="singleton-list">
              <inputCoverageBand>
                <coverageName>x_wind_10m</coverageName>
              </inputCoverageBand>
            </inputCoverageBands>
            <definition>x_wind_10m</definition>
            <index>0</index>
            <compositionType>BAND_SELECT</compositionType>
          </coverageBand>
          <coverageBand>
            <inputCoverageBands class="singleton-list">
              <inputCoverageBand>
                <coverageName>y_wind_10m</coverageName>
              </inputCoverageBand>
            </inputCoverageBands>
            <definition>y_wind_10m</definition>
            <index>1</index>
            <compositionType>BAND_SELECT</compositionType>
          </coverageBand>
        </coverageBands>
        <name>ceshi_coverage_01</name>
        <envelopeCompositionType>INTERSECTION</envelopeCompositionType>
        <selectedResolution>BEST</selectedResolution>
        <selectedResolutionIndex>-1</selectedResolutionIndex>
      </coverageView>
    </entry>
    <entry key="cachingEnabled">false</entry>
    <entry key="dirName">nmefc_wind_dir_xy_view_nmefc_wind</entry>
  </metadata>
  <store class="coverageStore">
    <name>my_test_2:nmefc_2016072112_opdr</name>
    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/my_test_2/coveragestores/nmefc_2016072112_opdr.xml" type="application/xml"/>
  </store>
  <nativeFormat>NetCDF</nativeFormat>
  <grid dimension="2">
    <range>
      <low>0 0</low>
      <high>251 251</high>
    </range>
    <transform>
      <scaleX>0.2</scaleX>
      <scaleY>-0.2</scaleY>
      <shearX>0.0</shearX>
      <shearY>0.0</shearY>
      <translateX>100.0</translateX>
      <translateY>50.0</translateY>
    </transform>
    <crs>EPSG:4326</crs>
  </grid>
  <supportedFormats>
    <string>GEOTIFF</string>
    <string>GIF</string>
    <string>PNG</string>
    <string>JPEG</string>
    <string>TIFF</string>
  </supportedFormats>
  <defaultInterpolationMethod>nearest neighbor</defaultInterpolationMethod>
  <dimensions>
    <coverageDimension>
      <name>x_wind_10m</name>
      <description>GridSampleDimension[-Infinity,Infinity]</description>
      <range>
        <min>-inf</min>
        <max>inf</max>
      </range>
      <dimensionType>
        <name>REAL_32BITS</name>
      </dimensionType>
    </coverageDimension>
    <coverageDimension>
      <name>y_wind_10m</name>
      <description>GridSampleDimension[-Infinity,Infinity]</description>
      <range>
        <min>-inf</min>
        <max>inf</max>
      </range>
      <dimensionType>
        <name>REAL_32BITS</name>
      </dimensionType>
    </coverageDimension>
  </dimensions>
  <requestSRS>
    <string>EPSG:4326</string>
  </requestSRS>
  <responseSRS>
    <string>EPSG:4326</string>
  </responseSRS>
  <parameters>
    <entry>
      <string>Bands</string>
      <null/>
    </entry>
    <entry>
      <string>Filter</string>
      <null/>
    </entry>
  </parameters>
  <nativeCoverageName>ceshi_coverage_01</nativeCoverageName>
</coverage>
                
        '''
    response = requests.post(
        f'http://localhost:8080/geoserver/rest/workspaces/{WORK_SPACE}/coveragestores/{coveragestore}/coverages',
        auth=('admin', 'geoserver'),
        data=msg,
        headers=headers_xml)
    pass


def bind_style_coverage():
    '''
        将 已经存在的 style 与 已经发布的 coverage 进行绑定
    '''
    style_name = 'wind_dir_style'
    sld_style = f'''
                
                        <layer>
                            <defaultStyle>
                                <name>{style_name}</name>
                            </defaultStyle>
                        </layer>
               '''
    url_cat = 'http://localhost:8080/geoserver/rest'
    cat = Catalog(url_cat, username='admin', password='geoserver')


def main():
    builder = coverage_xml()
    # create_nc_layer()
    # builder=info_xml()
    # 测试可行
    # builder=coverage_meta_xml()
    msg = tostring(builder.close(), encoding='utf-8', method='xml')
    print(msg)
    # 测试post 提交 coverage
    create_nc_coverage()
    pass


if __name__ == '__main__':
    main()
