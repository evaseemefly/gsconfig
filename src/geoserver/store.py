'''
gsconfig is a python library for manipulating a GeoServer instance via the GeoServer RESTConfig API.

The project is distributed under a MIT License .
'''

__author__ = "David Winslow"
__copyright__ = "Copyright 2012-2018 Boundless, Copyright 2010-2012 OpenPlans"
__license__ = "MIT"

import geoserver.workspace as ws
from geoserver.resource import featuretype_from_index, coverage_from_index, wmslayer_from_index
from geoserver.support import ResourceInfo, xml_property, key_value_pairs, write_bool, write_dict, write_string, \
    build_url
from geoserver.catalog import Catalog

try:
    from past.builtins import basestring
except ImportError:
    pass

# TODO:[-] 我自己加入的代码部分
from abc import ABCMeta, abstractmethod


class IStore(metaclass=ABCMeta):
    @property
    @abstractmethod
    def href(self):
        pass


def datastore_from_index(catalog, workspace, node):
    name = node.find("name")
    return DataStore(catalog, workspace, name.text)


def coveragestore_from_index(catalog, workspace, node):
    # TODO:[*] node是干嘛的？
    name = node.find("name")
    return CoverageStore(catalog, workspace, name.text)


def wmsstore_from_index(catalog, workspace, node):
    name = node.find("name")
    # user = node.find("user")
    # password = node.find("password")
    return WmsStore(catalog, workspace, name.text, None, None)


class DataStore(ResourceInfo, IStore):
    resource_type = "dataStore"
    save_method = "PUT"

    def __init__(self, catalog, workspace, name):
        super(DataStore, self).__init__()

        assert isinstance(workspace, ws.Workspace)
        assert isinstance(name, basestring)
        self.catalog = catalog
        self.workspace = workspace
        self.name = name

    @property
    def href(self):
        url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace.name,
                "datastores",
                self.name + ".xml"
            ]
        )
        return url

    enabled = xml_property("enabled", lambda x: x.text == "true")
    name = xml_property("name")
    type = xml_property("type")
    connection_parameters = xml_property("connectionParameters", key_value_pairs)

    writers = dict(
        enabled=write_bool("enabled"),
        name=write_string("name"),
        type=write_string("type"),
        connectionParameters=write_dict("connectionParameters")
    )

    @property
    def resource_url(self):
        url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace.name,
                "datastores",
                self.name,
                "featuretypes.xml"
            ]
        )
        return url

    def get_resources(self, name=None, available=False):
        res_url = self.resource_url
        if available:
            res_url += "?list=available"
        xml = self.catalog.get_xml(res_url)

        def ft_from_node(node):
            return featuretype_from_index(self.catalog, self.workspace, self, node)

        # if name passed, return only one FeatureType, otherwise return all FeatureTypes in store:
        if name is not None:
            for node in xml.findall("featureType"):
                if node.findtext("name") == name:
                    return ft_from_node(node)
            return None
        if available:
            return [str(node.text) for node in xml.findall("featureTypeName")]
        else:
            return [ft_from_node(node) for node in xml.findall("featureType")]


class UnsavedDataStore(DataStore, IStore):
    save_method = "POST"

    def __init__(self, catalog, name, workspace):
        super(UnsavedDataStore, self).__init__(catalog, workspace, name)
        self.dirty.update(dict(
            name=name, enabled=True, type=None,
            connectionParameters=dict()))

    @property
    def href(self):
        path = [
            "workspaces",
            self.workspace.name,
            "datastores"
        ]
        query = dict(name=self.name)
        return build_url(self.catalog.service_url, path, query)


class CoverageStore(ResourceInfo, IStore):
    # TODO:[-] 由于继承自ResourceInfo，由继承子类声明一个类变量，用来生成xml时的tag name时使用
    resource_type = 'coverageStore'
    save_method = "PUT"

    def __init__(self, catalog: Catalog, workspace: str, name: str):
        '''
            父类中定义了一个字典属性  self.dirty
        '''
        # ResourceInfo 构造函数中只声明了 dom 与 dirty(dict)
        super(CoverageStore, self).__init__()

        self.catalog = catalog
        self.workspace = workspace
        self.name = name

    @property
    def href(self):
        '''
            TODO:[-] 所有的ResourceInfo 实现类均需实现 href 属性方法(此处建议还是加入接口)
        '''
        url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace.name,
                "coveragestores",
                "{}.xml".format(self.name)
            ]
        )
        return url

    enabled = xml_property("enabled", lambda x: x.text == "true")
    name = xml_property("name")
    url = xml_property("url")
    type = xml_property("type")

    # TODO:[-] 主要为继承的 ResourceInfo 父类中的 def message -> def serialize 中调用
    writers = dict(
        enabled=write_bool("enabled"),
        name=write_string("name"),
        url=write_string("url"),
        type=write_string("type"),
        workspace=write_string("workspace")
    )

    def get_resources(self, name=None):
        '''
            TODO:[*] ? 何用？
        '''
        res_url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace.name,
                "coveragestores",
                self.name,
                "coverages.xml"
            ]
        )

        xml = self.catalog.get_xml(res_url)

        def cov_from_node(node):
            return coverage_from_index(self.catalog, self.workspace, self, node)

        # if name passed, return only one Coverage, otherwise return all Coverages in store:
        if name is not None:
            for node in xml.findall("coverage"):
                if node.findtext("name") == name:
                    return cov_from_node(node)
            return None
        return [cov_from_node(node) for node in xml.findall("coverage")]


class UnsavedCoverageStore(CoverageStore):
    '''
        未存储的 coverage store
    '''

    # 所有继承自ResourceInfo 的子类都需要声明 save_method 方法，用来指明 request的请求类型
    save_method = "POST"

    def __init__(self, catalog, name, workspace):
        super(UnsavedCoverageStore, self).__init__(catalog, workspace, name)
        self.dirty.update(
            name=name,
            enabled=True,
            type='GeoTIFF',
            url="file:data/",
            workspace=workspace
        )

    @property
    def href(self):
        # 'http://localhost:8082/geoserver/rest/workspaces/my_test_2/coveragestores?name=nmefc_2016072112_opdr_02'
        url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace,
                "coveragestores"
            ],
            dict(name=self.name)
        )
        return url


class UnsavedCoverageNcStore(CoverageStore):
    '''
        TODO:[*] + 20-03-17 创建了 nc store 的 CoverageStore 子类
    '''

    def __init__(self, catalog, name, workspace):
        super().__init__(catalog, workspace, name)
        self.dirty.update(
            name=name,
            enabled=True,
            type='NetCDF',
            url="file:data/",
            workspace=workspace
        )

    @property
    def href(self):
        '''
            重写的 unsaved 的 nc store 的提交 url
        '''
        # 'http://localhost:8082/geoserver/rest/workspaces/my_test_2/coveragestores?name=nmefc_2016072112_opdr_02'
        # f'http://localhost:8082/geoserver/rest/workspaces/{WORK_SPACE}/coveragestores/{coveragestore}/coverages'
        url = build_url(
            self.catalog.service_url,
            [
                "workspaces",
                self.workspace,
                "coveragestores",
                self.name,
                "coverages"
            ]
            # dict(name=self.name)
        )
        return url


class WmsStore(ResourceInfo):
    resource_type = "wmsStore"
    save_method = "PUT"

    def __init__(self, catalog, workspace, name, user, password):
        super(WmsStore, self).__init__()
        self.catalog = catalog
        self.workspace = workspace
        self.name = name
        self.metadata = {}
        self.metadata['user'] = user
        self.metadata['password'] = password

    @property
    def href(self):
        return "%s/workspaces/%s/wmsstores/%s.xml" % (self.catalog.service_url, self.workspace.name, self.name)

    enabled = xml_property("enabled", lambda x: x.text == "true")
    name = xml_property("name")
    nativeName = xml_property("nativeName")
    capabilitiesURL = xml_property("capabilitiesURL")
    type = xml_property("type")
    metadata = xml_property("metadata", key_value_pairs)

    writers = dict(enabled=write_bool("enabled"),
                   name=write_string("name"),
                   capabilitiesURL=write_string("capabilitiesURL"),
                   type=write_string("type"),
                   metadata=write_dict("metadata"))

    def get_resources(self, name=None, available=False):
        res_url = "{}/workspaces/{}/wmsstores/{}/wmslayers.xml".format(
            self.catalog.service_url,
            self.workspace.name,
            self.name
        )
        layer_name_attr = "wmsLayer"

        if available:
            res_url += "?list=available"
            layer_name_attr += 'Name'

        xml = self.catalog.get_xml(res_url)

        def wl_from_node(node):
            return wmslayer_from_index(self.catalog, self.workspace, self, node)

        # if name passed, return only one layer, otherwise return all layers in store:
        if name is not None:
            for node in xml.findall(layer_name_attr):
                if node.findtext("name") == name:
                    return wl_from_node(node)
            return None

        if available:
            return [str(node.text) for node in xml.findall(layer_name_attr)]
        else:
            return [wl_from_node(node) for node in xml.findall(layer_name_attr)]


class UnsavedWmsStore(WmsStore):
    save_method = "POST"

    def __init__(self, catalog, name, workspace, user, password):
        super(UnsavedWmsStore, self).__init__(catalog, workspace, name, user, password)
        metadata = {}
        if user is not None and password is not None:
            metadata['user'] = user
            metadata['password'] = password
        self.dirty.update(dict(
            name=name, enabled=True, capabilitiesURL="", type="WMS", metadata=metadata))

    @property
    def href(self):
        return "%s/workspaces/%s/wmsstores?name=%s" % (self.catalog.service_url, self.workspace.name, self.name)
