'''
gsconfig is a python library for manipulating a GeoServer instance via the GeoServer RESTConfig API.

The project is distributed under a MIT License .
'''

__author__ = "David Winslow"
__copyright__ = "Copyright 2012-2018 Boundless, Copyright 2010-2012 OpenPlans"
__license__ = "MIT"

import logging
from xml.etree.ElementTree import TreeBuilder, tostring
from tempfile import mkstemp
from zipfile import ZipFile
import os
import abc
# 新加入的
from abc import abstractclassmethod, abstractmethod
from typing import Callable

try:
    from urllib.parse import urljoin, quote, urlencode, urlparse
except ImportError:
    from urlparse import urljoin, urlparse
    from urllib import quote, urlencode

try:
    from past.builtins import basestring
except ImportError:
    pass

# TODO:[-] + 20-03-18 引入的 mid model
from mid_model import CoverageDimensionMidModel

logger = logging.getLogger("gsconfig.support")

FORCE_DECLARED = "FORCE_DECLARED"
# The projection handling policy for layers that should use coordinates
# directly while reporting the configured projection to clients.  This should be
# used when projection information is missing from the underlying datastore.


FORCE_NATIVE = "FORCE_NATIVE"
# The projection handling policy for layers that should use the projection
# information from the underlying storage mechanism directly, and ignore the
# projection setting.

REPROJECT = "REPROJECT"
# The projection handling policy for layers that should use the projection
# information from the underlying storage mechanism to reproject to the
# configured projection.
from typing import List


def build_url(base: str, seg: List[str], query: {} = None):
    """
    Create a URL from a list of path segments and an optional dict of query
    parameters.
    完成url的拼接工作，query干什么用的暂时没用到
    TODO:[-] 20-03-13
    大体的思路是：
        base 是基础url + seq 是需要拼接的一个list，拼接在base url 后面，然后query 是等于是查询的条件，直接 ?key=val的形式进行拼接
            base:'http://localhost:8082/geoserver/rest'
            seg:['workspaces', 'my_test_2', 'datastores.xml']
            query:{'name': 'nmefc_2016072112_opdr_02'}
            注意query是一个字典
    return:
        'http://localhost:8080/geoserver/rest/workspaces/ceshi/coveragestores?name=nmefc_2016072112_opdr_02'
    """

    def clean_segment(segment):
        """
        Cleans the segment and encodes to UTF-8 if the segment is unicode.
        """
        segment = segment.strip('/')
        if isinstance(segment, basestring):
            segment = segment.encode('utf-8')
        return segment

    # TODO:[*] ? 生成器
    seg = (quote(clean_segment(s)) for s in seg)
    if query is None or len(query) == 0:
        query_string = ''
    else:
        query_string = "?" + urlencode(query)
    # 'workspaces/my_test_2/datastores.xml'
    # query_string:'?name=nmefc_2016072112_opdr_02'
    # path:'workspaces/ceshi/coveragestores?name=nmefc_2016072112_opdr_02'
    path = '/'.join(seg) + query_string
    # TODO:[-]  对于base去掉右侧的 '/' 并加上 '/'
    adjusted_base = base.rstrip('/') + '/'

    # 'http://localhost:8080/geoserver/rest/workspaces/ceshi/coveragestores?name=nmefc_2016072112_opdr_02'
    return urljoin(str(adjusted_base), str(path))


def xml_property(path, converter=lambda x: x.text, default=None):
    '''
        TODO:[-] 在 store 中 会通过该方法进行读取xml中的节点的操作
                注意对xml的读取操作，可以参考此方法
                会在 store.py -> CoverageStore 中调用
    '''

    def getter(self):
        # ResourceInfo 中定义的一个字典被子类update
        # 判断指定的 path 是否在 ResourceInfo->dict中，若存在则取出
        # 为 support.py -> ResourceInfo 中定义的字典
        if path in self.dirty:
            return self.dirty[path]
        else:
            if self.dom is None:
                self.fetch()
            node = self.dom.find(path)
            # TODO:[*] converter 为一个lambda
            return converter(self.dom.find(path)) if node is not None else default

    def setter(self, value):
        self.dirty[path] = value

    def delete(self):
        self.dirty[path] = None

    # TODO:[*] ?
    return property(getter, setter, delete)


def bbox(node):
    if node is not None:
        minx = node.find("minx")
        maxx = node.find("maxx")
        miny = node.find("miny")
        maxy = node.find("maxy")
        crs = node.find("crs")
        crs = crs.text if crs is not None else None

        if (None not in [minx, maxx, miny, maxy]):
            return (minx.text, maxx.text, miny.text, maxy.text, crs)
        else:
            return None
    else:
        return None


def string_list(node):
    if node is not None:
        return [n.text for n in node.findall("string")]


def attribute_list(node):
    if node is not None:
        return [n.text for n in node.findall("attribute/name")]


def key_value_pairs(node):
    if node is not None:
        return dict((entry.attrib['key'], entry.text) for entry in node.findall("entry"))


def write_string(name):
    def write(builder: TreeBuilder, value: str):
        builder.start(name, dict())
        if (value is not None):
            builder.data(value)
        builder.end(name)

    return write


def write_bool(name):
    '''
        TODO:[*] 20-03-11 没太看懂，在所有的store中都定影了writers中调用
    '''

    def write(builder, b):
        builder.start(name, dict())
        builder.data("true" if b and b != "false" else "false")
        builder.end(name)

    return write


def write_bbox(name):
    def write(builder, b):
        builder.start(name, dict())
        bbox_xml(builder, b)
        builder.end(name)

    return write


def write_string_list(name):
    def write(builder, words):
        builder.start(name, dict())
        if words:
            words = [w for w in words if len(w) > 0]
            for w in words:
                builder.start("string", dict())
                builder.data(w)
                builder.end("string")
        builder.end(name)

    return write


def write_dict(name):
    def write(builder, pairs):
        builder.start(name, dict())
        for k, v in pairs.items():
            if k == 'port':
                v = str(v)
            builder.start("entry", dict(key=k))
            v = v if isinstance(v, basestring) else str(v)
            builder.data(v)
            builder.end("entry")
        builder.end(name)

    return write


def write_metadata(name):
    '''
        TODO:[*] !注意此方法 目前看此方法需要重写，或重新实现
    '''

    def write(builder, metadata):
        builder.start(name, dict())
        for k, v in metadata.items():
            builder.start("entry", dict(key=k))
            if k in ['time', 'elevation'] or k.startswith('custom_dimension'):
                dimension_info(builder, v)
            elif k == 'DynamicDefaultValues':
                dynamic_default_values_info(builder, v)
            elif k == 'JDBC_VIRTUAL_TABLE':
                jdbc_virtual_table(builder, v)
            else:
                builder.data(v)
            builder.end("entry")
        builder.end(name)

    return write


def write_metadata_nc(name) -> Callable[[TreeBuilder, dict], None]:
    def write(builder: TreeBuilder, metadata: dict) -> None:
        builder.start(name, dict())
        # 遍历传入的字典
        for k, v in metadata.items():
            builder.start("entry", dict(key=k))
            if k == "COVERAGE_VIEW":
                # 需要创建 coverageView
                coverageview_xml(builder, v)
        pass

    return write


class ResourceInfo(metaclass=abc.ABCMeta):
    '''
        TODO:[-] 20-03-09 需要由所有继承的子类实现一些方法，eg: href 等
    '''

    # TODO:[-] 20-03-11 # 所有继承自ResourceInfo 的子类都需要声明 save_method 方法，用来指明 request的请求类型
    def __init__(self):
        # TODO:[*] ? dom何用？
        self.dom = None
        # TODO:[*] 20-03-11 这个字典何用，被子类update
        self.dirty = dict()

    @property
    @abc.abstractmethod
    def href(self):
        '''
            TODO:[-] + 20-03-14 子类中必须要实现的 href 方法
        '''
        pass

    def fetch(self):
        # TODO:[-] 20-03-09 此处的self.href是什么？ self.catalog在哪里声明？ self.href 是需要由子类实现的属性方法
        # 注意看一下 layer line 105 继承自 ResourceInfo ，里面实现了 href 方法(property)
        # 调用时直接调用父类中的fetch 方法 获取对应的xml
        # self.catalog 在继承类中实现 eg: layer line 108
        self.dom = self.catalog.get_xml(self.href)

    def clear(self):
        self.dirty = dict()

    def refresh(self):
        self.clear()
        self.fetch()

    def serialize(self, builder: TreeBuilder):
        '''
            TODO:[*] 若只在 ResourceInfo 中由 message 调用话，建议是改为私有方法
        '''
        # TODO:[] 20-03-16 向builder 中遍历插入 self.dirty
        # GeoServer will disable the resource if we omit the <enabled> tag,
        # so force it into the dirty dict before writing
        if hasattr(self, "enabled"):
            self.dirty['enabled'] = self.enabled

        if hasattr(self, "advertised"):
            self.dirty['advertised'] = self.advertised

        # TODO:[-] ?此处的 writers 是什么？ 注意此处的 writers 在 store.py -> DataStore 中定义了 类属性 writers=dict(xx)
        for k, writer in self.writers.items():
            # todo:[-] ! 注意此处的 writer 是 store.py -> DataStore -> writers 中的字典,字典中val 对应的 是一个func(builder,b)——方法签名
            # 字典类型 { 'xx':func}
            if k in self.dirty:
                writer(builder, self.dirty[k])

    def message(self):
        '''
            # TODO:[-] 20-03-13 在ResourceInfo中定义的方法，最终返回的是需要提交的msg
            * 由于ResourceInfo是需要由子类继承的，所以self就是继承的子类
            eg: UnsavedCoverageStore
             message 为 TreeBuilder 创建的 Element -> str
        '''
        builder = TreeBuilder()
        # 创建了一个 resource_type(每个子类会声明这个类变量) 的 treebuilder
        builder.start(self.resource_type, dict())
        self.serialize(builder)
        builder.end(self.resource_type)
        # b'<coverageStore><enabled>true</enabled><name>nmefc_2016072112_opdr_02</name><url>file:nmefc/waterwind/nmefc_2016072112_opdr.nc</url><type>NetCDF</type><workspace>my_test_2</workspace></coverageStore>'
        msg = tostring(builder.close())
        return msg


def prepare_upload_bundle(name, data):
    """GeoServer's REST API uses ZIP archives as containers for file formats such
    as Shapefile and WorldImage which include several 'boxcar' files alongside
    the main data.  In such archives, GeoServer assumes that all of the relevant
    files will have the same base name and appropriate extensions, and live in
    the root of the ZIP archive.  This method produces a zip file that matches
    these expectations, based on a basename, and a dict of extensions to paths or
    file-like objects. The client code is responsible for deleting the zip
    archive when it's done."""
    fd, path = mkstemp()
    zip_file = ZipFile(path, 'w')
    for ext, stream in data.items():
        fname = "%s.%s" % (name, ext)
        if (isinstance(stream, basestring)):
            zip_file.write(stream, fname)
        else:
            zip_file.writestr(fname, stream.read())
    zip_file.close()
    os.close(fd)
    return path


def atom_link(node):
    if 'href' in node.attrib:
        return node.attrib['href']
    else:
        link = node.find("{http://www.w3.org/2005/Atom}link")
        return link.get('href')


def atom_link_xml(builder, href):
    builder.start("atom:link", {
        'rel': 'alternate',
        'href': href,
        'type': 'application/xml',
        'xmlns:atom': 'http://www.w3.org/2005/Atom'
    })
    builder.end("atom:link")


def bbox_xml(builder, box):
    minx, maxx, miny, maxy, crs = box
    builder.start("minx", dict())
    builder.data(minx)
    builder.end("minx")
    builder.start("maxx", dict())
    builder.data(maxx)
    builder.end("maxx")
    builder.start("miny", dict())
    builder.data(miny)
    builder.end("miny")
    builder.start("maxy", dict())
    builder.data(maxy)
    builder.end("maxy")
    if crs is not None:
        builder.start("crs", {"class": "projected"})
        builder.data(crs)
        builder.end("crs")


def coverageview_xml(info: dict):
    '''
        用来创建 coverageview 的 xml builder
    '''
    # TODO:[*] 20-03-18 可能引发错误
    # xml.etree.ElementTree.ParseError: multiple elements on top level
    root = TreeBuilder()
    root.start('coverage')
    for father_k, father_v in info.items():
        # 几个固定的
        if father_k.lower() == 'name':
            root.start(father_k, dict())
            root.data(father_v)
            root.end(father_k)
        elif father_k.lower() == 'nativename':
            root.start(father_k, dict())
            root.data(father_v)
            root.end(father_k)
        elif father_k.lower() == 'title':
            root.start(father_k, dict())
            root.data(father_v)
            root.end(father_k)
        elif father_k.lower() == 'nativecoveragename':
            root.start(father_k, dict())
            root.data(father_v)
            root.end(father_k)
        # 几个复杂类型
        # namespace :[name,atom]
        elif father_k.lower() == 'namespace':
            # root.start('namespace')
            coverageview_namespace_info(root, father_v, name='namespace')
            # root.end('namespace')
        # metadata
        elif father_k.lower() == 'metadata':
            # 创建 coverage stores -> data -> coverage ->  metadata -> entry :key='coverage_view' ->  coverageview
            coverageview_meta_info(root, father_v)
        elif father_k.lower() == 'dimensions':
            covreageview_dimensions_info(root, father_v, name='dimensions')
            pass
        # TODO:[-] + 20-03-19 新增的部分
        elif father_k.lower() in [temp.lower() for temp in ['enabled', 'nativeFormat', 'defaultInterpolationMethod']]:
            root.start(father_k)
            root.data(father_v)
            root.end(father_k)
        # 里面是嵌套的字典
        elif father_k.lower() in [temp.lower() for temp in ['requestSRS', 'responseSRS']]:
            root.start(father_k)
            if isinstance(father_v, dict):
                for k, v in father_v.items():
                    root.start(k)
                    root.data(v)
                    root.end(k)
            root.end(father_k)
        # store 节点
        elif father_k.lower() == 'store':
            coverageview_store_info(root, father_v)
            pass
            # root.start(father_v)
            # if isinstance(father_v,dict):
            #     for k,v in father_v.items():
            #
            # root.end(father_v)
    root.end('coverage')
    return root
    pass


def coverageview_namespace_info(builder: TreeBuilder, info: dict, name: str = None):
    '''
        TODO:[-] + 创建 namespace
                coverage stores -> data -> coverage -> [+] namespace
    '''
    if isinstance(info, dict):
        if name is not None:
            builder.start(name)
        for k, v in info.items():
            if k.lower() == 'name':
                builder.start(k)
                builder.data(v)
                builder.end(k)
            elif k.lower() == 'atom':
                builder.start(k)
                builder.data(v)
                builder.end(k)
        if name is not None:
            builder.end(name)


def coverageview_meta_info(builder: TreeBuilder, metadata: List[dict], name: str = None):
    '''
        TODO:[-] + 创建 coverageview

    '''
    # 此处需要加入判断metadata 是否为list
    if isinstance(metadata, list):
        # 目前存在的问题是 由于存在 coverageBands 是一个 coverageBand的数组，
        # 创建 coverage stores -> data -> coverage(root) -> [+]  metadata -> entry :key='coverage_view' ->  coverageview
        builder.start('metadata')
        # 下面需要改为循环一个数组
        for v in metadata:
            # if 'key' in v.items():
            if v.get('key').lower() == 'coverage_view':
                builder.start(v.get('name'), dict(key=v.get('key')))
                for k_1, v_1 in v.get('val').items():
                    # k_1: entry -> coverageView -> coverageBands
                    # v_1: entry -> coverageView -> coverageBands -[coverageband_1,coverageband_2]
                    if k_1.lower() == 'coverageview':
                        builder.start('coverageView')
                        for k_bands, v_bands in v_1.items():
                            if k_bands.lower() == 'coveragebands':
                                builder.start('coverageBands')
                                for k_band, v_band in v_bands.items():
                                    # k_band:'coverageband_1'
                                    # v_band: entry -> coverageView -> coverageBands- > {}
                                    coverageBand_info(builder, v_band)
                                builder.end('coverageBands')
                            elif k_bands.lower() in [temp.lower() for temp in
                                                     ['name', 'envelopeCompositionType', 'selectedResolution',
                                                      'selectedResolutionIndex']]:
                                builder.start(k_bands)
                                builder.data(v_bands)
                                builder.end(k_bands)
                            pass
                        builder.end('coverageView')

                builder.end(v.get('name'))
            elif v.get('key').lower() == 'cachingEnabled'.lower():
                builder.start(v.get('name'), dict(key=v.get('key')))
                builder.data(v.get('val'))
                builder.end(v.get('name'))
            elif v.get('key').lower() == 'dirName'.lower():
                builder.start(v.get('name'), dict(key=v.get('key')))
                builder.data(v.get('val'))
                builder.end(v.get('name'))

            # TODO:[*] 20-03-18 以下为暂时的备份
        # for k, v in metadata.items():
        #     if k.lower() == 'coverageview':
        #         # 创建 coverage stores -> data -> coverage ->  metadata -> [+] entry :key='coverage_view' -> coverageview
        #         builder.start('entry')
        #         # 创建 coverage stores -> data -> coverage ->  metadata -> entry :key='coverage_view' -> [+] coverageview
        #         # k: entry -> coverageView
        #         # v: entry -> coverageView -> coverageBands
        #         builder.start(k, dict())
        #         # 里面是一个数组，需要对数组进行循环
        #         for k_1, v_1 in v.items():
        #             # k_1: entry -> coverageView -> coverageBands
        #             # v_1: entry -> coverageView -> coverageBands -[coverageband_1,coverageband_2]
        #             if k_1.lower() == 'coveragebands':
        #                 builder.start('coverageBands')
        #                 for k_band, v_band in v_1.items():
        #                     # k_band:'coverageband_1'
        #                     # v_band: entry -> coverageView -> coverageBands- > {}
        #                     coverageBand_info(builder, v_band)
        #                 builder.end('coverageBands')
        #         pass
        #         builder.end(k)
        #         builder.end('entry')
        #
        builder.end('metadata')
        pass
    pass


def coverageview_store_info(builder: TreeBuilder, data: dict, name='store'):
    # if 'classname' in data.items():
    if data.get('classname'):
        builder.start(name, {'class': data.get('classname')})
        builder.start('name')
        builder.data(data.get('name', None))
        builder.end('name')
        builder.end(name)
        pass


def coverageBand_info(builder: TreeBuilder, data: dict):
    '''
        多路 band
    '''
    if isinstance(data, dict):
        builder.start('coverageBand')
        for k, v in data.items():
            # inputCoverageBands
            # definition
            # index
            # compositionType

            if k.lower() == 'definition':
                builder.start(k, dict())
                builder.data(str(v))
                builder.end(k)
                pass
            elif k.lower() == 'index':
                builder.start(k, dict())
                builder.data(str(v))
                builder.end(k)
                pass
            elif k.lower() == 'inputcoveragebands':
                builder.start(k, dict())
                for k_input, v_input in v.items():
                    if k_input.lower() == 'inputcoverageband':
                        builder.start(k_input, dict())
                        # if hasattr(v_input, 'coverageName'):
                        if v_input.get('coverageName'):
                            builder.start('coverageName', dict())
                            builder.data(v_input.get('coverageName'))
                            builder.end('coverageName')
                        builder.end(k_input)
                builder.end(k)
                pass
            elif k.lower() == 'compositiontype':
                builder.start(k, dict())
                builder.data(str(v))
                builder.end(k)
                pass

            # if ('coverageband' in k.lower()) and isinstance(v, dict):
            #     for k_band_temp, v_band_temp in v.items():
            #         #
            #         pass
            #
            # pass

            # 多路 band
            # if k.lower() == 'inputcoveragebands' and isinstance(v, dict):
            #     builder.start('coveragebands', dict())
            #     # coveragebands -> coverageband
            #     for k_band, v_band in v.items():
            #         #
            #         pass
            #     builder.end('coveragebands')
        builder.end('coverageBand')
    pass


def covreageview_dimensions_info(builder: TreeBuilder, data: dict, name: str = None):
    '''
        TODO:[-] + 创建 namespace
                coverage stores -> data -> coverage -> [+] dimensions
    '''
    # 将 dict -> dimensions 数组
    if isinstance(data, dict):
        if name is not None:
            builder.start(name)
        for k, v in data.items():
            if 'coveragedimension' in k.lower():
                # 是一个数组
                builder.start('coverageDimension')
                if isinstance(v, CoverageDimensionMidModel):
                    coverageDimension_info(builder, v)
                builder.end('coverageDimension')
                # for item in data.get('dimensions'):
        if name is not None:
            builder.end(name)
    pass


def coverageDimension_info(builder: TreeBuilder, data: CoverageDimensionMidModel):
    '''
        TODO:[-] + 创建 coverageDimension
                 coverage stores -> data -> coverage -> dimensions -> [+] coverageDimension
    '''
    if isinstance(data, CoverageDimensionMidModel):
        # name
        builder.start('name', dict())
        builder.data(data.name)
        builder.end('name')
        # desc
        builder.start('description')
        builder.data(data.des)
        builder.end('description')
        # type
        builder.start('dimensionType')
        builder.start('name')
        builder.data(data.type)
        builder.end('name')
        builder.end('dimensionType')
        #
        builder.start('range')
        builder.start('min')
        builder.data(data.range[0])
        builder.end('min')
        builder.start('max')
        builder.data(data.range[1])
        builder.end('max')
        builder.end('range')
    pass


def dimension_info(builder, metadata):
    if isinstance(metadata, DimensionInfo):
        builder.start("dimensionInfo", dict())
        builder.start("enabled", dict())
        builder.data("true" if metadata.enabled else "false")
        builder.end("enabled")
        if metadata.presentation is not None:
            accepted = ['LIST', 'DISCRETE_INTERVAL', 'CONTINUOUS_INTERVAL']
            if metadata.presentation not in accepted:
                raise ValueError("metadata.presentation must be one of the following %s" % accepted)
            else:
                builder.start("presentation", dict())
                builder.data(metadata.presentation)
                builder.end("presentation")
        if metadata.attribute is not None:
            builder.start("attribute", dict())
            builder.data(metadata.attribute)
            builder.end("attribute")
        if metadata.end_attribute is not None:
            builder.start("endAttribute", dict())
            builder.data(metadata.end_attribute)
            builder.end("endAttribute")
        if metadata.resolution is not None:
            builder.start("resolution", dict())
            builder.data(str(metadata.resolution_millis()))
            builder.end("resolution")
        if metadata.units is not None:
            builder.start("units", dict())
            builder.data(metadata.units)
            builder.end("units")
        if metadata.unitSymbol is not None:
            builder.start("unitSymbol", dict())
            builder.data(metadata.unitSymbol)
            builder.end("unitSymbol")
        if metadata.strategy is not None:
            builder.start("defaultValue", dict())
            builder.start("strategy", dict())
            builder.data(metadata.strategy)
            builder.end("strategy")
            if metadata.referenceValue:
                builder.start("referenceValue", dict())
                builder.data(metadata.referenceValue)
                builder.end("referenceValue")
            builder.end("defaultValue")
        if metadata.nearestMatchEnabled is not None:
            builder.start("nearestMatchEnabled", dict())
            builder.data(metadata.nearestMatchEnabled)
            builder.end("nearestMatchEnabled")

        builder.end("dimensionInfo")


class DimensionInfo(object):
    _lookup = (
        ('seconds', 1),
        ('minutes', 60),
        ('hours', 3600),
        ('days', 86400),
        # this is the number geoserver computes for 1 month
        ('months', 2628000000),
        ('years', 31536000000)
    )

    def __init__(self, name, enabled, presentation, resolution, units, unitSymbol,
                 strategy=None, attribute=None, end_attribute=None, reference_value=None, nearestMatchEnabled=None):
        self.name = name
        self.enabled = enabled
        self.attribute = attribute
        self.end_attribute = end_attribute
        self.presentation = presentation
        self.resolution = resolution
        self.units = units
        self.unitSymbol = unitSymbol
        self.strategy = strategy
        self.referenceValue = reference_value
        self.nearestMatchEnabled = nearestMatchEnabled

    def _multipier(self, name):
        name = name.lower()
        found = [i[1] for i in self._lookup if i[0] == name]
        if not found:
            raise ValueError('invalid multipler: %s' % name)
        return found[0] if found else None

    def resolution_millis(self):
        '''if set, get the value of resolution in milliseconds'''
        if self.resolution is None or not isinstance(self.resolution, basestring):
            return self.resolution
        val, mult = self.resolution.split(' ')
        return int(float(val) * self._multipier(mult) * 1000)

    def resolution_str(self):
        '''if set, get the value of resolution as "<n> <period>s", for example: "8 seconds"'''
        if self.resolution is None or isinstance(self.resolution, basestring):
            return self.resolution
        seconds = self.resolution / 1000.
        biggest = self._lookup[0]
        for entry in self._lookup:
            if seconds < entry[1]:
                break
            biggest = entry
        val = seconds / biggest[1]
        if val == int(val):
            val = int(val)
        return '%s %s' % (val, biggest[0])


def md_dimension_info(name, node):
    """Extract metadata Dimension Info from an xml node
        从 xml 节点中提取元数据维信息
    """

    def _get_value(child_name):
        return getattr(node.find(child_name), 'text', None)

    resolution = _get_value('resolution')
    defaultValue = node.find("defaultValue")
    strategy = defaultValue.find("strategy") if defaultValue is not None else None
    strategy = strategy.text if strategy is not None else None
    return DimensionInfo(
        name,
        _get_value('enabled') == 'true',
        _get_value('presentation'),
        int(resolution) if resolution else None,
        _get_value('units'),
        _get_value('unitSymbol'),
        strategy,
        _get_value('attribute'),
        _get_value('endAttribute'),
        _get_value('referenceValue'),
        _get_value('nearestMatchEnabled')
    )


def dynamic_default_values_info(builder, metadata):
    '''
        TODO:[*] 20-03-15 ?
    '''
    if isinstance(metadata, DynamicDefaultValues):
        builder.start("DynamicDefaultValues", dict())

        if metadata.configurations is not None:
            builder.start("configurations", dict())
            for c in metadata.configurations:
                builder.start("configuration", dict())
                if c.dimension is not None:
                    builder.start("dimension", dict())
                    builder.data(c.dimension)
                    builder.end("dimension")
                if c.policy is not None:
                    builder.start("policy", dict())
                    builder.data(c.policy)
                    builder.end("policy")
                if c.defaultValueExpression is not None:
                    builder.start("defaultValueExpression", dict())
                    builder.data(c.defaultValueExpression)
                    builder.end("defaultValueExpression")
                builder.end("configuration")
            builder.end("configurations")
        builder.end("DynamicDefaultValues")


class DynamicDefaultValuesConfiguration(object):
    def __init__(self, dimension, policy, defaultValueExpression):
        self.dimension = dimension
        self.policy = policy
        self.defaultValueExpression = defaultValueExpression


class DynamicDefaultValues(object):
    def __init__(self, name, configurations):
        self.name = name
        self.configurations = configurations


def md_dynamic_default_values_info(name, node):
    """Extract metadata Dynamic Default Values from an xml node"""
    configurations = node.find("configurations")
    if configurations is not None:
        configurations = []
        for n in node.findall("configuration"):
            dimension = n.find("dimension")
            dimension = dimension.text if dimension is not None else None
            policy = n.find("policy")
            policy = policy.text if policy is not None else None
            defaultValueExpression = n.find("defaultValueExpression")
            defaultValueExpression = defaultValueExpression.text if defaultValueExpression is not None else None

            configurations.append(DynamicDefaultValuesConfiguration(dimension, policy, defaultValueExpression))

    return DynamicDefaultValues(name, configurations)


class JDBCVirtualTableGeometry(object):
    def __init__(self, _name, _type, _srid):
        self.name = _name
        self.type = _type
        self.srid = _srid


class JDBCVirtualTableParam(object):
    def __init__(self, _name, _defaultValue, _regexpValidator):
        self.name = _name
        self.defaultValue = _defaultValue
        self.regexpValidator = _regexpValidator


class JDBCVirtualTable(object):
    def __init__(self, _name, _sql, _escapeSql, _geometry, _keyColumn=None, _parameters=None):
        self.name = _name
        self.sql = _sql
        self.escapeSql = _escapeSql
        self.geometry = _geometry
        self.keyColumn = _keyColumn
        self.parameters = _parameters


def jdbc_virtual_table(builder, metadata):
    if isinstance(metadata, JDBCVirtualTable):
        builder.start("virtualTable", dict())
        # name
        builder.start("name", dict())
        builder.data(metadata.name)
        builder.end("name")
        # sql
        builder.start("sql", dict())
        builder.data(metadata.sql)
        builder.end("sql")
        # escapeSql
        builder.start("escapeSql", dict())
        builder.data(metadata.escapeSql)
        builder.end("escapeSql")
        # keyColumn
        if metadata.keyColumn is not None:
            builder.start("keyColumn", dict())
            builder.data(metadata.keyColumn)
            builder.end("keyColumn")

        # geometry
        if metadata.geometry is not None:
            g = metadata.geometry
            builder.start("geometry", dict())
            if g.name is not None:
                builder.start("name", dict())
                builder.data(g.name)
                builder.end("name")
            if g.type is not None:
                builder.start("type", dict())
                builder.data(g.type)
                builder.end("type")
            if g.srid is not None:
                builder.start("srid", dict())
                builder.data(g.srid)
                builder.end("srid")
            builder.end("geometry")

        # parameters
        if metadata.parameters is not None:
            for p in metadata.parameters:
                builder.start("parameter", dict())
                if p.name is not None:
                    builder.start("name", dict())
                    builder.data(p.name)
                    builder.end("name")
                if p.defaultValue is not None:
                    builder.start("defaultValue", dict())
                    builder.data(p.defaultValue)
                    builder.end("defaultValue")
                if p.regexpValidator is not None:
                    builder.start("regexpValidator", dict())
                    builder.data(p.regexpValidator)
                    builder.end("regexpValidator")
                builder.end("parameter")

        builder.end("virtualTable")


def md_jdbc_virtual_table(key, node):
    """Extract metadata JDBC Virtual Tables from an xml node"""
    name = node.find("name")
    sql = node.find("sql")
    escapeSql = node.find("escapeSql")
    escapeSql = escapeSql.text if escapeSql is not None else None
    keyColumn = node.find("keyColumn")
    keyColumn = keyColumn.text if keyColumn is not None else None
    n_g = node.find("geometry")
    geometry = JDBCVirtualTableGeometry(n_g.find("name"), n_g.find("type"), n_g.find("srid"))
    parameters = []
    for n_p in node.findall("parameter"):
        p_name = n_p.find("name")
        p_defaultValue = n_p.find("defaultValue")
        p_defaultValue = p_defaultValue.text if p_defaultValue is not None else None
        p_regexpValidator = n_p.find("regexpValidator")
        p_regexpValidator = p_regexpValidator.text if p_regexpValidator is not None else None
        parameters.append(JDBCVirtualTableParam(p_name, p_defaultValue, p_regexpValidator))

    return JDBCVirtualTable(name, sql, escapeSql, geometry, keyColumn, parameters)


def md_entry(node):
    """Extract metadata entries from an xml node"""
    key = None
    value = None
    if 'key' in node.attrib:
        key = node.attrib['key']
    else:
        key = None

    if key in ['time', 'elevation'] or key.startswith('custom_dimension'):
        value = md_dimension_info(key, node.find("dimensionInfo"))
    elif key == 'DynamicDefaultValues':
        value = md_dynamic_default_values_info(key, node.find("DynamicDefaultValues"))
    elif key == 'JDBC_VIRTUAL_TABLE':
        value = md_jdbc_virtual_table(key, node.find("virtualTable"))
    else:
        value = node.text

    if None in [key, value]:
        return None
    else:
        return (key, value)


def metadata(node):
    if node is not None:
        return dict(md_entry(n) for n in node.findall("entry"))


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, basestring):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.items():
        if isinstance(key, basestring):
            key = key.encode('utf-8')
        if isinstance(value, basestring):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


def workspace_from_url(url):
    parts = urlparse(url)
    split_path = parts.path.split('/')
    if 'workspaces' in split_path:
        return split_path[split_path.index('workspaces') + 1]
    else:
        return None
