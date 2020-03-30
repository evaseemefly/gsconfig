from catalog import Catalog
from workspace import Workspace

class BaseCatalog:
    '''
        所有 cusotmer 子类需要继承的父类
    '''
    def __init__(self, cat: Catalog, work_space: str):
        '''

        @param cat: cat 实例
        @param work_space:  工作区名称
        '''
        self.cat = cat
        self.work_space = Workspace(cat,work_space)


