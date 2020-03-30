from catalog import Catalog
from customer_base import BaseCatalog


class CoverageNcStore(BaseCatalog):
    def __init__(self, cat: Catalog, work_space: str, store_name: str):
        '''

        @param cat: cat 实例
        @param work_space: 工作区名称
        @param store_name: 需要创建的 store title
        '''
        super().__init__(cat, work_space)
        self.store_name = store_name

    def create_nc_store(self, path: str):
        '''
            创建指定 nc store
        @param path:nc store的相对存储路径
        @return:
        '''
        # 需要先判断是否存在指定的 store
        if self.cat.get_store(self.store_name, self.work_space) is None:
            self.cat.create_coverageNCstore(self.store_name, self.work_space, create_layer=False, path=path)
        else:
            pass
