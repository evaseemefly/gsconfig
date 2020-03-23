from catalog import Catalog
from typing import List, Dict


class CoverageLayer:
    def __init__(self, catalog: Catalog, work_space: str):
        self.catalog = catalog
        self.work_space = work_space
        # self.layer_name=layer_name
        # self.store_name=store_name

    dict_meta = dict(
        coverageview=dict(
            # TODO:[-] + 加入的部分
            name='ceshi_coverage_01',
            envelopeCompositionType='INTERSECTION',
            selectedResolution='',
            selectedResolutionIndex='-1',
            # 之前的
            coveragebands=dict(
                # coverageband_1=dict(
                #     definition='x_wind_10m',
                #     index=0,
                #     inputcoveragebands=dict(
                #         inputcoverageband=dict(
                #             coverageName='x_wind_10m'
                #         )
                #     )
                # ),
                # coverageband_2=dict(
                #     definition='y_wind_10m',
                #     index=1,
                #     inputcoveragebands=dict(
                #         inputcoverageband=dict(
                #             coverageName='y_wind_10m'
                #         )
                #     )
                # ),
            )
        )
    )

    def create_layer(self, layer_name: str, store_name: str, bands: List[Dict[str, str]] = []):

        if self.check_exist_layer(layer_name) is None:
            if self.check_store(store_name):
                # 创建 新的layer
                # dict_meta -> coverageview -> name
                self.dict_meta.get('coverageview').update({'name': store_name})

                # dict_meta -> coverageview -> coveragebands -> coverageband_x
                for k, v in self.dict_meta.get('coverageview').get('coveragebands').items():
                    pass
                pass

                for i, v in enumerate(bands):
                    name = v.get('name')
                    BAND_NAME_PREFIX = 'coverageband'
                    # dict_meta -> coverageview -> coveragebands -> + coverageband_x
                    band_name_temp = f'{BAND_NAME_PREFIX}_{i}'
                    # band_dict_temp = {
                    #     band_name_temp: dict(
                    #         definition=name,
                    #         index=0,
                    #         inputcoveragebands=dict(
                    #             inputcoverageband=dict(
                    #                 coverageName=name
                    #             )
                    #         )
                    #     )}

                    self.dict_meta.get('coverageview').get('coveragebands').update({
                        band_name_temp: dict(
                            definition=name,
                            index=i,
                            inputcoveragebands=dict(
                                inputcoverageband=dict(
                                    coverageName=name
                                )
                            )
                        )
                    })
                    # print(i, v)

                    pass
                print(self.dict_meta)
                pass

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
