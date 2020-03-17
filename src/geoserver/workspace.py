'''
gsconfig is a python library for manipulating a GeoServer instance via the GeoServer RESTConfig API.

The project is distributed under a MIT License .
'''

__author__ = "David Winslow"
__copyright__ = "Copyright 2012-2018 Boundless, Copyright 2010-2012 OpenPlans"
__license__ = "MIT"

from geoserver.support import ResourceInfo, build_url
from geoserver.catalog import Catalog
from xml.etree.ElementTree import Element


class Workspace(ResourceInfo):
    resource_type = "workspace"

    def __init__(self, catalog: Catalog, name: str):
        '''
            name:workspace的名字
            catalog:Catalog
        '''
        super(Workspace, self).__init__()
        self.catalog = catalog
        self.name = name

    @property
    def href(self):
        return build_url(self.catalog.service_url, ["workspaces", self.name + ".xml"])

    @property
    def coveragestore_url(self):
        return build_url(self.catalog.service_url, ["workspaces", self.name, "coveragestores.xml"])

    @property
    def datastore_url(self):
        '''
            获取 data store 最终url
            最终 return 'http://localhost:8082/geoserver/rest/workspaces/my_test_2/datastores.xml'
        '''
        return build_url(self.catalog.service_url, ["workspaces", self.name, "datastores.xml"])

    @property
    def wmsstore_url(self):
        return "%s/workspaces/%s/wmsstores.xml" % (self.catalog.service_url, self.name)

    def __repr__(self):
        return "%s @ %s" % (self.name, self.href)


def workspace_from_index(catalog: Catalog, node) -> Workspace:
    '''
        node:<class 'xml.etree.ElementTree.Element'>
    '''
    name: Element = node.find("name")
    return Workspace(catalog, name.text)
