import requests
from xml.etree.ElementTree import tostring
from catalog import Catalog
from typing import List, Dict
from mid_model import CoverageDimensionMidModel
from support import coverageview_xml


class CoverageLayer:
    def __init__(self, catalog: Catalog, work_space: str, store_name: str):
        self.catalog = catalog
        self.work_space = work_space
        self.store_name = store_name
        # self.layer_name=layer_name
        # self.store_name=store_name

    @property
    def href(self):
        '''
            返回需要提交的url
            eg: http://localhost:8082/geoserver/rest/workspaces/Searchrescue/coveragestores/nmefc_wind_dir_xy/coverages
            对比:http://localhost:8082/geoserver/rest/workspaces/my_test_2/coveragestores/nmefc_wind/coverages
        '''
        return f'http://localhost:8080/geoserver/rest/workspaces/{self.work_space}/coveragestores/{self.store_name}/coverages'

    @property
    def msg(self):
        '''
            需要提交的 data
        '''
        builder = coverageview_xml(self.dict_coverage)
        msg = tostring(builder.close(), encoding='utf-8', method='xml')
        # print(msg)
        return msg

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
                val=None
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
    )

    dict_meta = dict(
        coverageview=dict(
            # TODO:[-] + 加入的部分
            name='ceshi_coverage_01',
            envelopeCompositionType='INTERSECTION',
            selectedResolution='BEST',
            selectedResolutionIndex='-1',
            coverageBands=dict(
            )
        )
    )

    def create_layer(self, layer_name: str, store_name: str, title: str, bands: List[Dict[str, str]] = []):

        # TODO:[*] 20-03-24 注意若存在指定的 layer 需要有处理，目前是直接返回None，在外侧处理
        if self.check_exist_layer(layer_name) is None:
            if self.check_store(store_name):
                # 创建 新的layer
                # 1 动态生成 dict_meta
                # 1.1
                # dict_meta -> coverageview -> name
                self.dict_meta.get('coverageview').update({'name': layer_name})

                # dict_meta -> coverageview -> coverageBands -> coverageband_x
                for k, v in self.dict_meta.get('coverageview').get('coverageBands').items():
                    pass
                pass
                # 1.2 在 dict_meta -> + bands
                for i, v in enumerate(bands):
                    name = v.get('name')
                    band_name_prefix = 'coverageband'
                    # dict_meta -> coverageview -> coverageBands -> + coverageband_x
                    band_name_temp = f'{band_name_prefix}_{i}'
                    self.dict_meta.get('coverageview').get('coverageBands').update({
                        band_name_temp: dict(
                            definition=name,
                            index=i,
                            inputCoverageBands=dict(
                                inputCoverageBand=dict(
                                    coverageName=name
                                )
                            )
                        )
                    })
                    # print(i, v)
                    pass
                # print(self.dict_meta)
                self._generate_coverage_dict(layer_name, store_name, layer_name, layer_name, bands)
                pass

    def _generate_coverage_dict(self, layer_name: str, store_name: str, title: str = None, native_name: str = None,
                                dimensions: List[Dict] = [],
                                **kwargs):
        '''
            动态生成 dict_coverage 字典 (all)
        '''
        if title is None:
            title = layer_name
        if native_name is None:
            native_name = layer_name
        # dict_coverage -> name
        self.dict_coverage.update({'name': layer_name})
        # dict_coverage -> nativeName
        self.dict_coverage.update({'nativeName': native_name})
        # dict_coverage -> namespace
        self.dict_coverage.update({'namespace': dict(
            name=self.work_space,
            atom=self.work_space
        )})
        # dict_coverage -> nativeCoverageName
        self.dict_coverage.update({
            'nativeCoverageName': native_name
        })
        # dict_coverage -> store
        self.dict_coverage.update({
            'store': dict(
                classname='coverageStore',
                name=f'{self.work_space}:{store_name}'
            )
        })

        # dict_coverage -> metadata
        self._update_metadata(native_name)
        # dict_coverage -> dimensions
        self._update_dimensions(dimensions)

    def _update_metadata(self, coverage_name: str):
        '''
            update -> metadata
        '''
        self.dict_coverage.update({'metadata': [
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
                val=coverage_name
            ),
            dict(
                key='COVERAGE_VIEW',
                name='entry',
                tag='',
                val=self.dict_meta
            ),
        ]})

    def _update_dimensions(self, dimensions: List[Dict]):
        '''
            update -> dimensions
        '''
        coverage_dimension_prefix = 'coverageDimension'
        coverage_dimension_dict = {}
        for k, v in enumerate(dimensions):
            coverage_dimension_dict.update({
                f'{coverage_dimension_prefix}_{k}': CoverageDimensionMidModel(v.get('name'),
                                                                              'GridSampleDimension[-Infinity,Infinity]',
                                                                              ['-inf', 'inf'], 'REAL_32BITS')
            })
        self.dict_coverage.update({
            'dimensions': coverage_dimension_dict
        })

    def check_exist_layer(self, name: str):
        '''
            判断是否存在指定名称的 layer
        '''
        return self.catalog.get_layer(name)
        pass

    def check_store(self, name: str):
        '''
            判断是否存在指定名称的 store
        '''
        return self.catalog.get_store(name, self.work_space)
        pass

    def publish(self, layer_name: str, bands: List[Dict[str, str]], store_name: str = None, title: str = None):
        '''
            发布 layer
        '''
        headers_xml = {'content-type': 'text/xml'}
        self.create_layer(layer_name, self.store_name, title if title else layer_name, bands)

        '''
             NOTE: 错误汇总:
                1- 400错误:No such layer: nmefc_wind
        '''

        response = requests.post(self.href, auth=('admin', 'geoserver'), data=self.msg, headers=headers_xml)
        if response.status_code in [200, 201]:
            return response
