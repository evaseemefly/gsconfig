from catalog import Catalog
# TODO:[-] 20-03-31 注意此处存在一个问题，由于修改了 gsconfig的源码，所以此处引用时是引用的系统环境中的 gsconfig(geoserver)
from geoserver.workspace import Workspace
# from workspace import Workspace

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


