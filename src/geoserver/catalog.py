# -*- coding: utf-8 -*-
'''
gsconfig is a python library for manipulating GeoServer via the GeoServer RESTConfig API

The project is distributed under a MIT License .
'''

__author__ = "David Winslow"
__copyright__ = "Copyright 2012-2018 Boundless, Copyright 2010-2012 OpenPlans"
__license__ = "MIT"

import sys

# TODO:[-] 20-03-12 此处使用修改后的gsconfig
# BUILD_SRC = r'D:\01proj\源码\gsconfig'
BUILD_SRC = r'/Users/evaseemefly/Documents/01Proj/部分源码/gis/gsconfig'
# caiwb 2020-03-26
BUILD_SRC = r'E:\Lab\python lab\gsconfig'
# sys.path.append(BUILD_SRC)

from datetime import datetime, timedelta
import logging
from geoserver.layer import Layer
from geoserver.resource import FeatureType
import sys
from conf.settings import ENV, DEV_ROOT_PATH

# TODO:[X] 注意加入了 开发模式
if ENV == 'DEV':
    BUILD_SRC = DEV_ROOT_PATH
    sys.path.append(BUILD_SRC)
    from src.geoserver.store import (
        coveragestore_from_index,
        datastore_from_index,
        wmsstore_from_index,
        UnsavedDataStore,
        UnsavedCoverageStore,
        UnsavedCoverageNcStore,
        UnsavedWmsStore
    )
else:
    from geoserver.store import (
        coveragestore_from_index,
        datastore_from_index,
        wmsstore_from_index,
        UnsavedDataStore,
        UnsavedCoverageStore,
        UnsavedWmsStore
    )

from geoserver.style import Style
from geoserver.support import prepare_upload_bundle, build_url
from geoserver.layergroup import LayerGroup, UnsavedLayerGroup
from geoserver.workspace import workspace_from_index, Workspace
import os
import re
from xml.etree.ElementTree import XML, Element
from xml.parsers.expat import ExpatError
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from typing import List

try:
    from past.builtins import basestring
except ImportError:
    pass

try:
    from urllib.parse import urlparse, urlencode, parse_qsl
except ImportError:
    from urlparse import urlparse, parse_qsl
    from urllib import urlencode

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

# TODO:[-] + 20-03-18 新加入的mid model
from mid_model import CoverageDimensionMidModel

logger = logging.getLogger("gsconfig.catalog")


class UploadError(Exception):
    pass


class ConflictingDataError(Exception):
    pass


class AmbiguousRequestError(Exception):
    pass


class FailedRequestError(Exception):
    pass


def _name(named):
    """Get the name out of an object.  This varies based on the type of the input:
       * the "name" of a string is itself
       * the "name" of None is itself
       * the "name" of an object with a property named name is that property -
         as long as it's a string
       * otherwise, we raise a ValueError
    """
    if isinstance(named, basestring) or named is None:
        return named
    elif hasattr(named, 'name') and isinstance(named.name, basestring):
        return named.name
    else:
        raise ValueError("Can't interpret %s as a name or a configuration object" % named)


class Catalog(object):
    """
    The GeoServer catalog represents all of the information in the GeoServer
    configuration.    This includes:
    - Stores of geospatial data
    - Resources, or individual coherent datasets within stores
    - Styles for resources
    - Layers, which combine styles with resources to create a visible map layer
    - LayerGroups, which alias one or more layers for convenience
    - Workspaces, which provide logical grouping of Stores
    - Maps, which provide a set of OWS services with a subset of the server's
        Layers
    - Namespaces, which provide unique identifiers for resources
    """

    def __init__(self, service_url: str, username="admin", password="geoserver", validate_ssl_certificate=True,
                 access_token=None):
        #
        # TODO:[*] 注意一下此处的 service_url 由 str 被拆分为 数组
        self.service_url: List[str] = service_url.strip("/")
        self.username = username
        self.password = password
        self.validate_ssl_certificate = validate_ssl_certificate
        self.access_token = access_token
        self.setup_connection()

        # TODO:[*] 何用？缓存
        self._cache = {}
        self._version = None

    def __getstate__(self):
        '''http connection cannot be pickled'''
        state = dict(vars(self))
        state.pop('http', None)
        state['http'] = None
        return state

    def __setstate__(self, state):
        '''restore http connection upon unpickling'''
        self.__dict__.update(state)
        self.setup_connection()

    def setup_connection(self):
        self.client = requests.session()
        self.client.verify = self.validate_ssl_certificate
        parsed_url = urlparse(self.service_url)
        retry = Retry(
            total=6,
            status=6,
            backoff_factor=0.9,
            status_forcelist=[502, 503, 504],
            method_whitelist=set(['HEAD', 'TRACE', 'GET', 'PUT', 'POST', 'OPTIONS', 'DELETE'])
        )

        self.client.mount("{}://".format(parsed_url.scheme), HTTPAdapter(max_retries=retry))

    def http_request(self, url, data=None, method='get', headers={}):
        '''
            TODO:[-] 主要是和认证有关系
        '''
        req_method = getattr(self.client, method.lower())

        if self.access_token:
            headers['Authorization'] = "Bearer {}".format(self.access_token)
            parsed_url = urlparse(url)
            params = parse_qsl(parsed_url.query.strip())
            params.append(('access_token', self.access_token))
            params = urlencode(params)
            url = "{proto}://{address}{path}?{params}".format(proto=parsed_url.scheme, address=parsed_url.netloc,
                                                              path=parsed_url.path, params=params)

            resp = req_method(url, headers=headers, data=data)
        else:
            resp = req_method(url, headers=headers, data=data, auth=(self.username, self.password))
        return resp

    def get_version(self):
        '''obtain the version or just 2.2.x if < 2.3.x
        Raises:
            FailedRequestError: If the request fails.
        '''
        if self._version:
            return self._version
        url = "{}/about/version.xml".format(self.service_url)
        resp = self.http_request(url)
        version = None
        if resp.status_code == 200:
            dom = XML(resp.content)
            resources = dom.findall("resource")
            for resource in resources:
                if resource.attrib["name"] == "GeoServer":
                    try:
                        version = resource.find("Version").text
                        break
                    except AttributeError:
                        pass

        # This will raise an exception if the catalog is not available
        # If the catalog is available but could not return version information,
        # it is an old version that does not support that
        if version is None:
            # just to inform that version < 2.3.x
            version = "2.2.x"
        self._version = version
        return version

    def get_short_version(self):
        '''obtain the shory geoserver version
        '''
        gs_version = self.get_version()
        match = re.compile(r'[^\d.]+')
        return match.sub('', gs_version).strip('.')

    def delete(self, config_object, purge=None, recurse=False):
        """
        send a delete request
        XXX [more here]
        """
        rest_url = config_object.href
        params = []

        # purge deletes the SLD from disk when a style is deleted
        if purge:
            params.append("purge=" + str(purge))

        # recurse deletes the resource when a layer is deleted.
        if recurse:
            params.append("recurse=true")

        if params:
            rest_url = rest_url + "?" + "&".join(params)

        headers = {
            "Content-type": "application/xml",
            "Accept": "application/xml"
        }

        resp = self.http_request(rest_url, method='delete', headers=headers)
        if resp.status_code != 200:
            raise FailedRequestError('Failed to make DELETE request: {}, {}'.format(resp.status_code, resp.text))

        self._cache.clear()

        # do we really need to return anything other than None?
        return (resp)

    def get_xml(self, rest_url: str) -> Element:
        '''
            大体的思路就是将 rest_url中的 response.content 转换为xml对象 Element
        '''
        # TODO:[*]
        cached_response = self._cache.get(rest_url)

        def is_valid(cached_response):
            return cached_response is not None and datetime.now() - cached_response[0] < timedelta(seconds=5)

        def parse_or_raise(xml: str) -> XML:
            '''
                将传入的xml_str 转成xml 对象

            '''
            try:
                return XML(xml)
            except (ExpatError, SyntaxError) as e:
                msg = "GeoServer gave non-XML response for [GET %s]: %s"
                msg = msg % (rest_url, xml)
                raise Exception(msg, e)

        if is_valid(cached_response):
            raw_text = cached_response[1]
            return parse_or_raise(raw_text)
        else:
            # 做一个认证
            resp = self.http_request(rest_url)
            if resp.status_code == 200:
                #
                '''
                    content:
                    b'<workspaces>\n  <workspace>\n    <name>cite</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/cite.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>tiger</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/tiger.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>nurc</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/nurc.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>sde</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/sde.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>it.geosolutions</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/it.geosolutions.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>topp</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/topp.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>sf</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/sf.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>my_test_2</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/my_test_2.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>my_test</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/my_test.xml" type="application/atom+xml"/>\n  </workspace>\n  <workspace>\n    <name>SearchRescue</name>\n    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" rel="alternate" href="http://localhost:8082/geoserver/rest/workspaces/SearchRescue.xml" type="application/atom+xml"/>\n  </workspace>\n</workspaces>'
                '''
                # 将 rest_url 作为 key，response.content作为val 存储在_cache字典中
                self._cache[rest_url] = (datetime.now(), resp.content)
                return parse_or_raise(resp.content)
            else:
                raise FailedRequestError(resp.content)

    def reload(self):
        url = "{}/reload".format(self.service_url)
        resp = self.http_request(url, method='post')
        self._cache.clear()
        return resp

    def reset(self):
        url = "{}/reset".format(self.service_url)
        resp = self.http_request(url, method='post')
        self._cache.clear()
        return resp

    def save(self, obj, content_type="application/xml"):
        """
        TODO:[-] 20-03-13 将message xml->str，并提交 geoserver rest
                只有在 Catalog -> create_coveragestore -> self.save中调用
                在 create_coveragestore 使用中，调用了save方法，传入的obj是要被存储(也就是提交到geoserver rest)的对象
                此时的obj是 UnsavedCoverageStore
                将具体实现的 store 获取 message (由父类 ResourceInfo 实现 message 方法)
                obj:UnsaveCoverageStore 等
        TODO:[-] 20-03-14 save 主要是用来创建 store 的，目前看nc可以直接使用，不需要重写此方法
        saves an object to the REST service
        gets the object's REST location and the data from the object,
        then POSTS the request.
        """

        # 'http://localhost:8082/geoserver/rest/workspaces/my_test_2/coveragestores?name=nmefc_2016072112_opdr_02'
        rest_url = obj.href
        #
        data = obj.message()

        headers = {
            "Content-type": content_type,
            "Accept": content_type
        }

        logger.debug("{} {}".format(obj.save_method, obj.href))
        resp = self.http_request(rest_url, method=obj.save_method.lower(), data=data, headers=headers)

        if resp.status_code not in (200, 201):
            raise FailedRequestError('Failed to save to Geoserver catalog: {}, {}'.format(resp.status_code, resp.text))

        self._cache.clear()
        return resp

    def _return_first_item(self, _list):
        if len(_list) == 0:
            return None
        elif len(_list) > 1:
            raise AmbiguousRequestError("Multiple items found")
        else:
            return _list[0]

    def get_stores(self, names=None, workspaces=None):
        '''
          Returns a list of stores in the catalog. If workspaces is specified will only return stores in those workspaces.
          从 catalog 返回 stores列表，若指定了名称则只返回匹配的store
          返回类型为 geoserver.store 中的store实现
          If names is specified, will only return stores that match.
          names can either be a comma delimited string or an array.
          Will return an empty list if no stores are found.
        '''

        if isinstance(workspaces, Workspace):
            workspaces = [workspaces]
        elif isinstance(workspaces, list) and [w for w in workspaces if isinstance(w, Workspace)]:
            # nothing
            pass
        else:
            workspaces = self.get_workspaces(names=workspaces)

        stores = []

        # TODO: 20-03-13 从workspaces 中遍历,获取data store coverage store 与 wms store 的所有的list
        for ws in workspaces:
            ds_list: Element = self.get_xml(ws.datastore_url)
            cs_list: Element = self.get_xml(ws.coveragestore_url)
            wms_list: Element = self.get_xml(ws.wmsstore_url)
            # TODO:[*] 比较重要
            # 从 ds_list 中找到所有的 dataStore 的节点
            stores.extend([datastore_from_index(self, ws, n) for n in ds_list.findall("dataStore")])
            stores.extend([coveragestore_from_index(self, ws, n) for n in cs_list.findall("coverageStore")])
            stores.extend([wmsstore_from_index(self, ws, n) for n in wms_list.findall("wmsStore")])

        if names is None:
            names = []
        elif isinstance(names, basestring):
            names = [s.strip() for s in names.split(',') if s.strip()]

        if stores and names:
            return ([store for store in stores if store.name in names])

        return stores

    def get_store(self, name, workspace=None):
        '''
          Returns a single store object.
          Will return None if no store is found.
          Will raise an error if more than one store with the same name is found.
        '''

        stores = self.get_stores(workspaces=workspace, names=name)
        return self._return_first_item(stores)

    def create_datastore(self, name, workspace=None):
        if isinstance(workspace, basestring):
            workspace = self.get_workspaces(names=workspace)[0]
        elif workspace is None:
            workspace = self.get_default_workspace()
        return UnsavedDataStore(self, name, workspace)

    def create_wmsstore(self, name, workspace=None, user=None, password=None):
        if workspace is None:
            workspace = self.get_default_workspace()
        return UnsavedWmsStore(self, name, workspace, user, password)

    def create_wmslayer(self, workspace, store, name, nativeName=None):
        '''
            TODO:[*] 20-03-04 在Catalog中并不存在直接 create layer的方法
        '''
        headers = {
            "Content-type": "text/xml",
            "Accept": "application/xml"
        }
        # if not provided, fallback to name - this is what geoserver will do
        # anyway but nativeName needs to be provided if name is invalid xml
        # as this will cause verification errors since geoserver 2.6.1
        if nativeName is None:
            nativeName = name

        url = store.href.replace('.xml', '/wmslayers')
        data = "<wmsLayer><name>{}</name><nativeName>{}</nativeName></wmsLayer>".format(name, nativeName)
        resp = self.http_request(url, method='post', data=data, headers=headers)

        if resp.status_code not in (200, 201):
            raise FailedRequestError('Failed to create WMS layer: {}, {}'.format(resp.status_code, resp.text))

        self._cache.clear()
        return self.get_layer(name)

    def add_data_to_store(self, store, name, data, workspace=None, overwrite=False, charset=None):
        if isinstance(store, basestring):
            store = self.get_stores(names=store, workspaces=workspace)[0]
        if workspace is not None:
            workspace = _name(workspace)
            assert store.workspace.name == workspace, "Specified store (%s) is not in specified workspace (%s)!" % (
                store, workspace)
        else:
            workspace = store.workspace.name
        store = store.name

        if isinstance(data, dict):
            bundle = prepare_upload_bundle(name, data)
        else:
            bundle = data

        params = dict()
        if overwrite:
            params["update"] = "overwrite"
        if charset is not None:
            params["charset"] = charset
        params["filename"] = "{}.zip".format(name)
        params["target"] = "shp"
        # params["configure"] = "all"

        headers = {'Content-Type': 'application/zip', 'Accept': 'application/xml'}
        upload_url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace,
                "datastores",
                store,
                "file.shp"
            ],
            params
        )

        try:
            with open(bundle, "rb") as f:
                data = f.read()
                resp = self.http_request(upload_url, method='put', data=data, headers=headers)
                if resp.status_code != 201:
                    FailedRequestError(
                        'Failed to add data to store {} : {}, {}'.format(store, resp.status_code, resp.text))
                self._cache.clear()
        finally:
            # os.unlink(bundle)
            pass

    def create_featurestore(self, name, data, workspace=None, overwrite=False, charset=None):
        if workspace is None:
            workspace = self.get_default_workspace()
        workspace = _name(workspace)

        if not overwrite:
            stores = self.get_stores(names=name, workspaces=workspace)
            if len(stores) > 0:
                msg = "There is already a store named {} in workspace {}".format(name, workspace)
                raise ConflictingDataError(msg)

        params = dict()
        if charset is not None:
            params['charset'] = charset
        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace,
                "datastores",
                name,
                "file.shp"
            ],
            params
        )

        # PUT /workspaces/<ws>/datastores/<ds>/file.shp
        headers = {
            "Content-type": "application/zip",
            "Accept": "application/xml"
        }
        if isinstance(data, dict):
            logger.debug('Data is NOT a zipfile')
            archive = prepare_upload_bundle(name, data)
        else:
            logger.debug('Data is a zipfile')
            archive = data
        file_obj = open(archive, 'rb')
        try:
            resp = self.http_request(url, method='put', data=file_obj, headers=headers)
            if resp.status_code != 201:
                FailedRequestError(
                    'Failed to create FeatureStore {} : {}, {}'.format(name, resp.status_code, resp.text))
            self._cache.clear()
        finally:
            file_obj.close()
            os.unlink(archive)

    def create_imagemosaic(self, name, data, configure='first', workspace=None, overwrite=False, charset=None):
        if workspace is None:
            workspace = self.get_default_workspace()
        workspace = _name(workspace)

        if not overwrite:
            store = self.get_stores(names=name, workspaces=workspace)
            if store:
                raise ConflictingDataError("There is already a store named {}".format(name))

        params = dict()
        if charset is not None:
            params['charset'] = charset
        if configure.lower() not in ('first', 'none', 'all'):
            raise ValueError("configure most be one of: first, none, all")
        params['configure'] = configure.lower()

        store_type = "file.imagemosaic"
        contet_type = "application/zip"

        if hasattr(data, 'read'):
            # Adding this check only to pass tests. We should drop support for passing a file object
            upload_data = data
        elif isinstance(data, basestring):
            if os.path.splitext(data)[-1] == ".zip":
                upload_data = open(data, 'rb')
            else:
                store_type = "external.imagemosaic"
                contet_type = "text/plain"
                upload_data = data if data.startswith("file:") else "file:{data}".format(data=data)
        else:
            raise ValueError("ImageMosaic Dataset or directory: {data} is incorrect".format(data=data))

        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace,
                "coveragestores",
                name,
                store_type
            ],
            params
        )

        # PUT /workspaces/<ws>/coveragestores/<name>/file.imagemosaic?configure=none
        headers = {
            "Content-type": contet_type,
            "Accept": "application/xml"
        }

        try:
            resp = self.http_request(url, method='put', data=upload_data, headers=headers)
            if resp.status_code != 201:
                FailedRequestError('Failed to create ImageMosaic {} : {}, {}'.format(name, resp.status_code, resp.text))
            self._cache.clear()
        finally:
            if hasattr(upload_data, "close"):
                upload_data.close()

        return self.get_stores(names=name, workspaces=workspace)[0]

    def create_coveragestore(self, name, workspace=None, path=None, type='GeoTIFF',
                             create_layer=True, layer_name=None, source_name=None, upload_data=False,
                             contet_type="image/tiff"):
        """
        TODO:[-] 目前看支持的type不包含nc,已改造
                layer_name 为创建的图层的名称
                source_name 为栅格中的band的名称
                对于提交的 coverage layer 发现他的处理很简单，只是拼接 url与 data ，并未嵌套其他的dict
                20-03-14 鉴于此方法无法满足提交定制化的 多band的data(nc)，准备新实现一个create方法
        TODO:[*] 此处存在一个问题就是对于多band的情况，可能会有问题
        Create a coveragestore for locally hosted rasters.
        If create_layer is set to true, will create a coverage/layer.
        layer_name and source_name are only used if create_layer ia enabled.
        If not specified, the raster name will be used for both.
        """
        if path is None:
            raise Exception('You must provide a full path to the raster')

        if layer_name is not None and ":" in layer_name:
            ws_name, layer_name = layer_name.split(':')

        allowed_types = [
            'ImageMosaic',
            'GeoTIFF',
            'Gtopo30',
            'WorldImage',
            'AIG',
            'ArcGrid',
            'DTED',
            'EHdr',
            'ERDASImg',
            'ENVIHdr',
            'GeoPackage (mosaic)',
            'NITF',
            'RPFTOC',
            'RST',
            'VRT',
            'NetCDF'  # 新加入了nc格式的支持
        ]

        if type is None:
            raise Exception('Type must be declared')
        elif type not in allowed_types:
            raise Exception('Type must be one of {}'.format(", ".join(allowed_types)))

        if workspace is None:
            workspace = self.get_default_workspace()
        workspace = _name(workspace)

        # TODO:[-] 此处他大概判断一下是否需要上传文件，若需要上传文件，则读取本地文件，并上传。但并不支持复杂的data的拼接
        # 我的方式还是将nc原始文件直接复制到服务端的指定路径下，不需要上传功能
        if upload_data is False:
            # TODO:[-] unSaved是需要创建的store(可以放在创建layer中时调用，也可以独立出来)
            # TODO:[*] 此处存在一个问题，若是指定ws中已经存在了指定store，后台会报错，此处需要加入一个判断
            cs = UnsavedCoverageStore(self, name, workspace)
            # TODO:[*] 20-03-13 此处赋值的type与url好像不存在该属性？
            cs.type = type
            cs.url = path if path.startswith("file:") else "file:{}".format(path)
            # TODO:[-] 所有的的 create layer 都会先提交 store，也就是在 catalog.save 提交 store，再执行后续的操作
            self.save(cs)

            # 对传入的文件 名(包含后缀)进行拆分，取出文件名(不含后缀)
            if create_layer:
                if layer_name is None:
                    layer_name = os.path.splitext(os.path.basename(path))[0]
                if source_name is None:
                    source_name = os.path.splitext(os.path.basename(path))[0]
                # 此处再看一下之前研究的xml
                data = "<coverage><name>{}</name><nativeName>{}</nativeName></coverage>".format(layer_name, source_name)
                url = "{}/workspaces/{}/coveragestores/{}/coverages.xml".format(self.service_url, workspace, name)
                headers = {"Content-type": "application/xml"}

                resp = self.http_request(url, method='post', data=data, headers=headers)
                if resp.status_code != 201:
                    FailedRequestError('Failed to create coverage/layer {} for : {}, {}'.format(layer_name, name,
                                                                                                resp.status_code,
                                                                                                resp.text))
                self._cache.clear()
                return self.get_resources(names=layer_name, workspaces=workspace)[0]
        # 以下提交的data是通过读取后再put提交，不使用此种方式
        else:
            data = open(path, 'rb')
            params = {"configure": "first", "coverageName": name}
            url = build_url(
                self.service_url,
                # 以下的list是seq，为一个集合，在build_url 方法里面 进行拼接
                [
                    "workspaces",
                    workspace,
                    "coveragestores",
                    name,
                    "file.{}".format(type.lower())
                ],
                params
            )

            headers = {"Content-type": contet_type}
            resp = self.http_request(url, method='put', data=data, headers=headers)

            if hasattr(data, "close"):
                data.close()

            if resp.status_code != 201:
                FailedRequestError(
                    'Failed to create coverage/layer {} for : {}, {}'.format(layer_name, name, resp.status_code,
                                                                             resp.text))

        return self.get_stores(names=name, workspaces=workspace)[0]

    def create_coverageNCstore(self, name: str, workspace=None, path=None, store_type='netcdf', create_layer=True,
                               layer_name=None, source_name=None, bands_names=[]):
        '''
            TODO:[*] 20-03-14 ~ 03-17 自己实现的 nc coverage 方法
            准备自己实现的创建 nc 格式的coverage layer
        '''
        if path is None:
            raise Exception('需要填入栅格数据全路径')
        # 对于有 : 间隔的 layer_name 需要根据 ：拆分
        if layer_name is not None and ":" in layer_name:
            ws_name, layer_name = layer_name.split(':')

        # 由于目前本方法只处理 nc 格式的数据
        allowed_types: List[str] = [
            'netcdf'
        ]
        if store_type is None:
            raise Exception('未提供type')
        if store_type.lower() not in allowed_types:
            raise Exception(f'{store_type}未支持')

        if workspace is None:
            workspace = self.get_default_workspace()
        workspace_name = _name(workspace)

        # 下面为主要的改写的内容
        '''
            大体思路：
                1- 创建 unsavedCoverageStore
                2- 调用 save方法
                3- 发送post请求
        '''
        cs = UnsavedCoverageStore(self, name, workspace_name)
        cs.type = store_type
        cs.url = path if path.startswith("file:") else "file:{}".format(path)
        self.save(cs)
        # TODO:[!] 此部分比较重要: 需要创建 layer
        if create_layer:
            if layer_name is None:
                layer_name = os.path.splitext(os.path.basename(path))[0]
            if source_name is None:
                source_name = os.path.splitext(os.path.basename(path))[0]
        # TODO:[-] 此处为难点，需要生成一个提交的data
        # TODO:[*] 20-03-17 将之前错误放置在 layer 中的生成 xml的方法放在此处
        # TODO:[*] 20-03-20 将 case.py -> create_nc_coverage放在此处(已测试成功)
        # TODO:[*] 20-03-20 当创建完coverage layer 后，需要手动的设置该 layer 的 style
        headers_xml = {'content-type': 'text/xml'}
        url_style=f'http://localhost:8082/geoserver/rest//workspaces/{WORK_SPACE}/layers/{coverage_title}'
        xml_style=f'''
                        <layer>
                            <defaultStyle>
                                <name>{style_name}</name>
                            </defaultStyle>
                        </layer>
                    '''
        response=requests.put(
            url_style,
            auth=('admin','geoserver'),
            data=xml_style,
            headers=headers_xml
        )
        pass

    def add_granule(self, data, store, workspace=None):
        '''Harvest/add a granule into an existing imagemosaic'''
        ext = os.path.splitext(data)[-1]
        if ext == ".zip":
            type = "file.imagemosaic"
            upload_data = open(data, 'rb')
            headers = {
                "Content-type": "application/zip",
                "Accept": "application/xml"
            }
        else:
            type = "external.imagemosaic"
            upload_data = data if data.startswith("file:") else "file:{data}".format(data=data)
            headers = {
                "Content-type": "text/plain",
                "Accept": "application/xml"
            }

        params = dict()
        workspace_name = workspace
        if isinstance(store, basestring):
            store_name = store
        else:
            store_name = store.name
            workspace_name = store.workspace.name

        if workspace_name is None:
            raise ValueError("Must specify workspace")

        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace_name,
                "coveragestores",
                store_name,
                type
            ],
            params
        )

        try:
            resp = self.http_request(url, method='post', data=upload_data, headers=headers)
            if resp.status_code != 202:
                FailedRequestError(
                    'Failed to add granule to mosaic {} : {}, {}'.format(store, resp.status_code, resp.text))
            self._cache.clear()
        finally:
            if hasattr(upload_data, "close"):
                upload_data.close()

        # maybe return a list of all granules?
        return None

    def delete_granule(self, coverage, store, granule_id, workspace=None):
        '''Deletes a granule of an existing imagemosaic'''
        params = dict()

        workspace_name = workspace
        if isinstance(store, basestring):
            store_name = store
        else:
            store_name = store.name
            workspace_name = store.workspace.name

        if workspace_name is None:
            raise ValueError("Must specify workspace")

        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace_name,
                "coveragestores",
                store_name,
                "coverages",
                coverage,
                "index/granules",
                granule_id,
                ".json"
            ],
            params
        )

        # DELETE /workspaces/<ws>/coveragestores/<name>/coverages/<coverage>/index/granules/<granule_id>.json
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json"
        }

        resp = self.http_request(url, method='delete', headers=headers)
        if resp.status_code != 200:
            FailedRequestError(
                'Failed to delete granule from mosaic {} : {}, {}'.format(store, resp.status_code, resp.text))
        self._cache.clear()

        # maybe return a list of all granules?
        return None

    def list_granules(self, coverage, store, workspace=None, filter=None, limit=None, offset=None):
        '''List granules of an imagemosaic'''
        params = dict()

        if filter is not None:
            params['filter'] = filter
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset

        workspace_name = workspace
        if isinstance(store, basestring):
            store_name = store
        else:
            store_name = store.name
            workspace_name = store.workspace.name

        if workspace_name is None:
            raise ValueError("Must specify workspace")

        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace_name,
                "coveragestores",
                store_name,
                "coverages",
                coverage,
                "index/granules.json"
            ],
            params
        )

        # GET /workspaces/<ws>/coveragestores/<name>/coverages/<coverage>/index/granules.json
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json"
        }

        resp = self.http_request(url, headers=headers)
        if resp.status_code != 200:
            FailedRequestError(
                'Failed to list granules in mosaic {} : {}, {}'.format(store, resp.status_code, resp.text))

        self._cache.clear()
        return resp.json()

    def mosaic_coverages(self, store):
        '''Returns all coverages in a coverage store'''
        params = dict()
        url = build_url(
            self.service_url,
            [
                "workspaces",
                store.workspace.name,
                "coveragestores",
                store.name,
                "coverages.json"
            ],
            params
        )
        # GET /workspaces/<ws>/coveragestores/<name>/coverages.json
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json"
        }

        resp = self.http_request(url, headers=headers)
        if resp.status_code != 200:
            FailedRequestError('Failed to get mosaic coverages {} : {}, {}'.format(store, resp.status_code, resp.text))

        self._cache.clear()
        return resp.json()

    def mosaic_coverage_schema(self, coverage, store, workspace):
        '''Returns the schema of a coverage in a coverage store'''
        params = dict()
        url = build_url(
            self.service_url,
            [
                "workspaces",
                workspace,
                "coveragestores",
                store,
                "coverages",
                coverage,
                "index.json"
            ],
            params
        )
        # GET /workspaces/<ws>/coveragestores/<name>/coverages/<coverage>/index.json

        headers = {
            "Content-type": "application/json",
            "Accept": "application/json"
        }

        resp = self.http_request(url, headers=headers)
        if resp.status_code != 200:
            FailedRequestError('Failed to get mosaic schema {} : {}, {}'.format(store, resp.status_code, resp.text))

        self._cache.clear()
        return resp.json()

    def publish_featuretype(self, name, store, native_crs, srs=None, jdbc_virtual_table=None, native_name=None):
        '''Publish a featuretype from data in an existing store'''
        # @todo native_srs doesn't seem to get detected, even when in the DB
        # metadata (at least for postgis in geometry_columns) and then there
        # will be a misconfigured layer
        if native_crs is None:
            raise ValueError("must specify native_crs")

        srs = srs or native_crs
        feature_type = FeatureType(self, store.workspace, store, name)
        # because name is the in FeatureType base class, work around that
        # and hack in these others that don't have xml properties
        feature_type.dirty['name'] = name
        feature_type.dirty['srs'] = srs
        feature_type.dirty['nativeCRS'] = native_crs
        feature_type.enabled = True
        feature_type.advertised = True
        feature_type.title = name

        if native_name is not None:
            feature_type.native_name = native_name

        headers = {
            "Content-type": "application/xml",
            "Accept": "application/xml"
        }

        resource_url = store.resource_url
        if jdbc_virtual_table is not None:
            feature_type.metadata = ({'JDBC_VIRTUAL_TABLE': jdbc_virtual_table})
            params = dict()
            resource_url = build_url(
                self.service_url,
                [
                    "workspaces",
                    store.workspace.name,
                    "datastores", store.name,
                    "featuretypes.xml"
                ],
                params
            )

        resp = self.http_request(resource_url, method='post', data=feature_type.message(), headers=headers)
        if resp.status_code not in (200, 201, 202):
            FailedRequestError('Failed to publish feature type {} : {}, {}'.format(name, resp.status_code, resp.text))

        self._cache.clear()
        feature_type.fetch()
        return feature_type

    def get_resources(self, names=None, stores=None, workspaces=None):
        '''
        Resources include feature stores, coverage stores and WMS stores, however does not include layer groups.
        names, stores and workspaces can be provided as a comma delimited strings or as arrays, and are used for filtering.
        Will always return an array.
        资源包括特性库、覆盖库和WMS库，但是不包括层组。
        名称、存储和工作区可以作为逗号分隔的字符串或数组提供，并用于筛选。
        将始终返回一个数组。
        '''

        stores = self.get_stores(
            names=stores,
            workspaces=workspaces
        )

        resources = []
        for s in stores:
            try:
                resources.extend(s.get_resources())
            except FailedRequestError:
                continue

        if names is None:
            names = []
        elif isinstance(names, basestring):
            names = [s.strip() for s in names.split(',') if s.strip()]

        if resources and names:
            return ([resource for resource in resources if resource.name in names])

        return resources

    def get_resource(self, name=None, store=None, workspace=None):
        '''
          returns a single resource object.
          Will return None if no resource is found.
          Will raise an error if more than one resource with the same name is found.
        '''

        resources = self.get_resources(names=name, stores=store, workspaces=workspace)
        return self._return_first_item(resources)

    def get_layer(self, name):
        try:
            lyr = Layer(self, name)
            lyr.fetch()
            return lyr
        except FailedRequestError:
            return None

    def get_layers(self, resource=None):
        '''
            TODO:[*] 此处调用了 self.get_xml
        '''
        if isinstance(resource, basestring):
            if self.get_short_version() >= "2.13":
                if ":" in resource:
                    ws_name, resource = resource.split(':')

            resource = self.get_resources(names=resource)[0]
        layers_url = "{}/layers.xml".format(self.service_url)
        data = self.get_xml(layers_url)
        lyrs = [Layer(self, l.find("name").text) for l in data.findall("layer")]
        if resource is not None:
            lyrs = [l for l in lyrs if l.resource.href == resource.href]
        # TODO: Filter by style
        return lyrs

    def get_layergroups(self, names=None, workspaces=None):
        '''
        names and workspaces can be provided as a comma delimited strings or as arrays, and are used for filtering.
        If no workspaces are provided, will return all layer groups in the catalog (global and workspace specific).
        Will always return an array.
        '''

        layergroups = []

        if workspaces is None or len(workspaces) == 0:
            # Add global layergroups
            url = "{}/layergroups.xml".format(self.service_url)
            groups = self.get_xml(url)
            layergroups.extend([LayerGroup(self, g.find("name").text, None) for g in groups.findall("layerGroup")])
            workspaces = []
        elif isinstance(workspaces, basestring):
            workspaces = [s.strip() for s in workspaces.split(',') if s.strip()]
        elif isinstance(workspaces, Workspace):
            workspaces = [workspaces]

        if not workspaces:
            workspaces = self.get_workspaces()

        for ws in workspaces:
            ws_name = _name(ws)
            url = "{}/workspaces/{}/layergroups.xml".format(self.service_url, ws_name)
            try:
                groups = self.get_xml(url)
            except FailedRequestError as e:
                if "no such workspace" in str(e).lower():
                    continue
                else:
                    raise FailedRequestError("Failed to get layergroups: {}".format(e))

            layergroups.extend([LayerGroup(self, g.find("name").text, ws_name) for g in groups.findall("layerGroup")])

        if names is None:
            names = []
        elif isinstance(names, basestring):
            names = [s.strip() for s in names.split(',') if s.strip()]

        if layergroups and names:
            return ([lg for lg in layergroups if lg.name in names])

        return layergroups

    def get_layergroup(self, name, workspace=None):
        '''
          returns a single layergroup object.
          Will return None if no layergroup is found.
          Will raise an error if more than one layergroup with the same name is found.
        '''

        layergroups = self.get_layergroups(names=name, workspaces=workspace)
        return self._return_first_item(layergroups)

    def create_layergroup(self, name, layers=(), styles=(), bounds=None, mode="SINGLE", abstract=None,
                          title=None, workspace=None):
        if self.get_layergroups(names=name, workspaces=workspace):
            raise ConflictingDataError("LayerGroup named %s already exists!" % name)
        else:
            return UnsavedLayerGroup(self, name, layers, styles, bounds, mode, abstract, title, workspace)

    def get_styles(self, names=None, workspaces=None):
        '''
        names and workspaces can be provided as a comma delimited strings or as arrays, and are used for filtering.
        If no workspaces are provided, will return all styles in the catalog (global and workspace specific).
        Will always return an array.
        '''

        all_styles = []

        if workspaces is None:
            # Add global styles
            url = "{}/styles.xml".format(self.service_url)
            styles = self.get_xml(url)
            all_styles.extend([Style(self, s.find('name').text) for s in styles.findall("style")])
            workspaces = []
        elif isinstance(workspaces, basestring):
            workspaces = [s.strip() for s in workspaces.split(',') if s.strip()]
        elif isinstance(workspaces, Workspace):
            workspaces = [workspaces]

        if not workspaces:
            workspaces = self.get_workspaces()

        for ws in workspaces:
            url = "{}/workspaces/{}/styles.xml".format(self.service_url, _name(ws))
            try:
                styles = self.get_xml(url)
            except FailedRequestError as e:
                if "no such workspace" in str(e).lower():
                    continue
                elif "workspace {} not found".format(_name(ws)) in str(e).lower():
                    continue
                else:
                    raise FailedRequestError("Failed to get styles: {}".format(e))

            all_styles.extend([Style(self, s.find("name").text, _name(ws)) for s in styles.findall("style")])

        if names is None:
            names = []
        elif isinstance(names, basestring):
            names = [s.strip() for s in names.split(',') if s.strip()]

        if all_styles and names:
            return ([style for style in all_styles if style.name in names])

        return all_styles

    def get_style(self, name, workspace=None):
        '''
          returns a single style object.
          Will return None if no style is found.
          Will raise an error if more than one style with the same name is found.
        '''

        styles = self.get_styles(names=name, workspaces=workspace)
        return self._return_first_item(styles)

    def create_style(self, name, data, overwrite=False, workspace=None, style_format="sld10", raw=False):
        styles = self.get_styles(names=name, workspaces=workspace)
        if len(styles) > 0:
            style = styles[0]
        else:
            style = None

        if not overwrite and style is not None:
            raise ConflictingDataError("There is already a style named %s" % name)

        if style is None:
            headers = {
                "Content-type": "application/xml",
                "Accept": "application/xml"
            }
            xml = "<style><name>{0}</name><filename>{0}.sld</filename></style>".format(name)
            style = Style(self, name, workspace, style_format)

            resp = self.http_request(style.create_href, method='post', data=xml, headers=headers)
            if resp.status_code not in (200, 201, 202):
                FailedRequestError('Failed to create style {} : {}, {}'.format(name, resp.status_code, resp.text))

        headers = {
            "Content-type": style.content_type,
            "Accept": "application/xml"
        }

        body_href = style.body_href
        if raw:
            body_href += "?raw=true"

        resp = self.http_request(body_href, method='put', data=data, headers=headers)
        if resp.status_code not in (200, 201, 202):
            FailedRequestError('Failed to create style {} : {}, {}'.format(name, resp.status_code, resp.text))

        self._cache.pop(style.href, None)
        self._cache.pop(style.body_href, None)

    def create_workspace(self, name, uri):
        '''
            TODO:[-] 20-03-09 提交netcdf的操作可以参考此方法，实际也是将xml拼接之后 post
        '''
        xml = (
            "<namespace>"
            "<prefix>{name}</prefix>"
            "<uri>{uri}</uri>"
            "</namespace>"
        ).format(name=name, uri=uri)

        headers = {"Content-Type": "application/xml"}
        workspace_url = self.service_url + "/namespaces/"

        resp = self.http_request(workspace_url, method='post', data=xml, headers=headers)
        if resp.status_code not in (200, 201, 202):
            FailedRequestError('Failed to create workspace {} : {}, {}'.format(name, resp.status_code, resp.text))

        self._cache.pop("{}/workspaces.xml".format(self.service_url), None)
        workspaces = self.get_workspaces(names=name)
        # Can only have one workspace with this name
        return workspaces[0] if workspaces else None

    def get_workspaces(self, names: List[str] = None):
        '''
            返回 在 names 中的 workspaces
          Returns a list of workspaces in the catalog.
          If names is specified, will only return workspaces that match.
          names can either be a comma delimited string or an array.
          Will return an empty list if no workspaces are found.
        '''
        if names is None:
            names = []
        elif isinstance(names, basestring):
            names = [s.strip() for s in names.split(',') if s.strip()]
        # 
        data: Element = self.get_xml("{}/workspaces.xml".format(self.service_url))
        workspaces: List[Workspace] = []
        # 找到所有包含workspace的节点
        workspaces.extend([workspace_from_index(self, node) for node in data.findall("workspace")])

        if workspaces and names:
            return ([ws for ws in workspaces if ws.name in names])

        return workspaces

    def get_workspace(self, name):
        '''
          returns a single workspace object.
          Will return None if no workspace is found.
          Will raise an error if more than one workspace with the same name is found.
          返回单个工作空间对象。
          如果找不到工作空间，将返回None。
          如果找到多个具有相同名称的工作空间，将引发错误。
        '''

        workspaces = self.get_workspaces(names=name)
        return self._return_first_item(workspaces)

    def get_default_workspace(self):
        '''
            获取默认的工作空间
        '''
        ws = Workspace(self, "default")
        # must fetch and resolve the 'real' workspace from the response
        ws.fetch()
        return workspace_from_index(self, ws.dom)

    def set_default_workspace(self, name):
        if hasattr(name, 'name'):
            name = name.name
        workspace = self.get_workspaces(names=name)[0]
        if workspace is not None:
            headers = {"Content-Type": "application/xml"}
            default_workspace_url = self.service_url + "/workspaces/default.xml"
            data = "<workspace><name>{}</name></workspace>".format(name)

            resp = self.http_request(default_workspace_url, method='put', data=data, headers=headers)
            if resp.status_code not in (200, 201, 202):
                FailedRequestError(
                    'Failed to set default workspace {} : {}, {}'.format(name, resp.status_code, resp.text))

            self._cache.pop(default_workspace_url, None)
            self._cache.pop("{}/workspaces.xml".format(self.service_url), None)
        else:
            raise FailedRequestError("no workspace named {}".format(name))

    def list_feature_type_names(self, workspace, store, filter='available'):
        if workspace is None:
            raise ValueError("Must provide workspace")

        if store is None:
            raise ValueError("Must provide store")

        filter = filter.lower()
        workspace = _name(workspace)
        store = _name(store)

        url = "{}/workspaces/{}/datastores/{}/featuretypes.json?list={}".format(self.service_url, workspace, store,
                                                                                filter)
        resp = self.http_request(url)
        if resp.status_code != 200:
            FailedRequestError('Failed to query feature_type_names')

        data = []
        if filter in ('available', 'available_with_geom'):
            try:
                data = resp.json()['list']['string']
            except JSONDecodeError:
                pass
            return data
        elif filter == 'configured':
            data = resp.json()['featureTypes']['featureType']
            return [fn['name'] for fn in data]
        elif filter == 'all':
            feature_type_names = []
            url = "{}/workspaces/{}/datastores/{}/featuretypes.json?list=available".format(self.service_url, workspace,
                                                                                           store)
            resp = self.http_request(url)
            if resp.status_code != 200:
                FailedRequestError('Failed to query feature_type_names')
            feature_type_names.extend(resp.json()['list']['string'])

            url = "{}/workspaces/{}/datastores/{}/featuretypes.json?list=configured".format(self.service_url, workspace,
                                                                                            store)
            resp = self.http_request(url)
            if resp.status_code != 200:
                FailedRequestError('Failed to query feature_type_names')
            data = resp.json()['featureTypes']['featureType']
            feature_type_names.extend([fn['name'] for fn in data])

            return feature_type_names
