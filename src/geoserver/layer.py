'''
gsconfig is a python library for manipulating a GeoServer instance via the GeoServer RESTConfig API.

The project is distributed under a MIT License .
'''

__author__ = "David Winslow"
__copyright__ = "Copyright 2012-2018 Boundless, Copyright 2010-2012 OpenPlans"
__license__ = "MIT"

from xml.etree.ElementTree import XML, Element, ElementTree
from typing import Dict
from geoserver.support import ResourceInfo, xml_property, write_bool, workspace_from_url
from geoserver.style import Style
from geoserver.catalog import Catalog


class _attribution(object):
    def __init__(self, title, width, height, href, url, type):
        self.title = title
        self.width = width
        self.height = height
        self.href = href
        self.url = url
        self.type = type


def _read_attribution(node):
    title = node.find("title")
    width = node.find("logoWidth")
    height = node.find("logoHeight")
    href = node.find("href")
    url = node.find("logoURL")
    type = node.find("logoType")

    if title is not None:
        title = title.text
    if width is not None:
        width = width.text
    if height is not None:
        height = height.text
    if href is not None:
        href = href.text
    if url is not None:
        url = url.text
    if type is not None:
        type = type.text

    return _attribution(title, width, height, href, url, type)


def _write_attribution(builder, attr):
    builder.start("attribution", dict())
    if attr.title is not None:
        builder.start("title", dict())
        builder.data(attr.title)
        builder.end("title")
    if attr.width is not None:
        builder.start("logoWidth", dict())
        builder.data(attr.width)
        builder.end("logoWidth")
    if attr.height is not None:
        builder.start("logoHeight", dict())
        builder.data(attr.height)
        builder.end("logoHeight")
    if attr.href is not None:
        builder.start("href", dict())
        builder.data(attr.href)
        builder.end("href")
    if attr.url is not None:
        builder.start("logoURL", dict())
        builder.data(attr.url)
        builder.end("logoURL")
    if attr.type is not None:
        builder.start("logoType", dict())
        builder.data(attr.type)
        builder.end("logoType")
    builder.end("attribution")


def _write_style_element(builder, name):
    ws, name = name.split(':') if ':' in name else (None, name)
    builder.start("name", dict())
    builder.data(name)
    builder.end("name")
    if ws:
        builder.start("workspace", dict())
        builder.data(ws)
        builder.end("workspace")


def _write_default_style(builder, name):
    builder.start("defaultStyle", dict())
    if name is not None:
        _write_style_element(builder, name)
    builder.end("defaultStyle")


def _write_alternate_styles(builder, styles):
    builder.start("styles", dict())
    for s in styles:
        builder.start("style", dict())
        _write_style_element(builder, getattr(s, 'fqn', s))
        builder.end("style")
    builder.end("styles")


class Layer(ResourceInfo):
    def __init__(self, catalog: Catalog, name: str):
        super(Layer, self).__init__()
        # TODO:[-] 在所有实现类的构造函数中定义 catalog
        self.catalog = catalog
        self.name = name
        self.gs_version = self.catalog.get_short_version()

    resource_type = "layer"
    save_method = "PUT"

    @property
    def href(self):
        return "{}/layers/{}.xml".format(self.catalog.service_url, self.name)

    @property
    def resource(self):
        '''
            TODO:[*] 何用？ 我的理解layer里面没有msg，有reources
        '''
        if self.dom is None:
            self.fetch()
        name = self.dom.find("resource/name").text
        atom_link = [n for n in self.dom.find("resource").getchildren() if 'href' in n.attrib]
        ws_name = workspace_from_url(atom_link[0].get('href'))
        if self.gs_version >= "2.13":
            if ":" in name:
                ws_name, name = name.split(':')
        return self.catalog.get_resources(names=name, workspaces=ws_name)[0]

    def _get_default_style(self):
        if 'default_style' in self.dirty:
            return self.dirty['default_style']
        if self.dom is None:
            self.fetch()
        element = self.dom.find("defaultStyle")
        # aborted data uploads can result in no default style
        return self._resolve_style(element) if element is not None else None

    def _resolve_style(self, element):
        if ":" in element.find('name').text:
            ws_name, style_name = element.find('name').text.split(':')
        else:
            style_name = element.find('name').text
            ws_name = None
        atom_link = [n for n in element.getchildren() if 'href' in n.attrib]
        if atom_link and ws_name is None:
            ws_name = workspace_from_url(atom_link[0].get("href"))
        return self.catalog.get_styles(names=style_name, workspaces=ws_name)[0]

    def _set_default_style(self, style):
        if isinstance(style, Style):
            style = style.fqn
        self.dirty["default_style"] = style

    def _get_alternate_styles(self):
        if "alternate_styles" in self.dirty:
            return self.dirty["alternate_styles"]
        if self.dom is None:
            self.fetch()
        styles_list = self.dom.findall("styles/style")
        return [self._resolve_style(s) for s in styles_list]

    def _set_alternate_styles(self, styles):
        self.dirty["alternate_styles"] = styles

    default_style = property(_get_default_style, _set_default_style)
    styles = property(_get_alternate_styles, _set_alternate_styles)

    attribution_object = xml_property("attribution", _read_attribution)
    enabled = xml_property("enabled", lambda x: x.text == "true")
    advertised = xml_property("advertised", lambda x: x.text == "true", default=True)
    type = xml_property("type")

    def _get_attr_attribution(self):
        obj = {
            'title': self.attribution_object.title,
            'width': self.attribution_object.width,
            'height': self.attribution_object.height,
            'href': self.attribution_object.href,
            'url': self.attribution_object.url,
            'type': self.attribution_object.type
        }
        return obj

    def _set_attr_attribution(self, attribution):
        self.dirty["attribution"] = _attribution(
            attribution['title'],
            attribution['width'],
            attribution['height'],
            attribution['href'],
            attribution['url'],
            attribution['type']
        )

        assert self.attribution_object.title == attribution['title']
        assert self.attribution_object.width == attribution['width']
        assert self.attribution_object.height == attribution['height']
        assert self.attribution_object.href == attribution['href']
        assert self.attribution_object.url == attribution['url']
        assert self.attribution_object.type == attribution['type']

    attribution = property(_get_attr_attribution, _set_attr_attribution)

    writers = dict(
        attribution=_write_attribution,
        enabled=write_bool("enabled"),
        advertised=write_bool("advertised"),
        default_style=_write_default_style,
        alternate_styles=_write_alternate_styles
    )


class CoverageLayer(Layer):
    '''
        TODO:[!] + 20-03-14 新建的用来创建 coverage layer
    '''

    def __init__(self, catalog: Catalog, name: str):
        super().__init__(catalog, name)
        root_node = (
            {'key': 'name', 'val': self.name}
        )
        pass

    @property
    def _base_msg_str(self):
        '''
            基础 base xml
            先创建一个基础的 xml 然后向其中插入动态的节点数据，先去掉所有的动态数据的节点

        '''
        base_xml_str = f'''
                    <coverage>
  <namespace>
</namespace>  
  <description>Generated from NetCDF</description>
  <keywords>    
    <string>WCS</string>
    <string>NetCDF</string>
  </keywords>
  <nativeCRS>GEOGCS["WGS 84", DATUM["World Geodetic System 1984", SPHEROID["WGS 84", 6378137.0, 298.257223563, AUTHORITY["EPSG","7030"]], AUTHORITY["EPSG","6326"]], PRIMEM["Greenwich", 0.0, AUTHORITY["EPSG","8901"]], UNIT["degree", 0.017453292519943295], AXIS["Geodetic longitude", EAST], AXIS["Geodetic latitude", NORTH], AUTHORITY["EPSG","4326"]]</nativeCRS>
  <srs>EPSG:4326</srs>
  <nativeBoundingBox>
    <minx>99.9</minx>
    <maxx>150.10000000000002</maxx>
    <miny>-0.1</miny>
    <maxy>50.1</maxy>
    <crs>EPSG:4326</crs>
  </nativeBoundingBox>
  <latLonBoundingBox>
    <minx>99.9</minx>
    <maxx>150.10000000000002</maxx>
    <miny>-0.1</miny>
    <maxy>50.1</maxy>
    <crs>EPSG:4326</crs>
  </latLonBoundingBox>
  <projectionPolicy>REPROJECT_TO_DECLARED</projectionPolicy>
  <enabled>true</enabled>
  <metadata>
    <entry key="COVERAGE_VIEW">
      <coverageView>
        <coverageBands>
        </coverageBands>        
        <envelopeCompositionType>INTERSECTION</envelopeCompositionType>
        <selectedResolution>BEST</selectedResolution>
        <selectedResolutionIndex>-1</selectedResolutionIndex>
      </coverageView>
    </entry>
    <entry key="cachingEnabled">false</entry>
    <entry key="dirName">nmefc_wind_dir_xy_view_nmefc_wind</entry>
  </metadata>
  <store class="coverageStore">
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
  <interpolationMethods>
    <string>nearest neighbor</string>
    <string>bilinear</string>
    <string>bicubic</string>
  </interpolationMethods>
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
</coverage>
                    '''
        return base_xml_str

    @property
    def base_msg(self) -> ElementTree:
        '''
            返回当前的 base_msg xml对象
        '''
        base_msg_xml = XML(self._base_msg_str)
        return base_msg_xml

    def insert_node(self, node: Dict[str, str], singleton=True):
        '''
            node:传入的{key,val} 节点
            singleton:是否是单例节点
        '''
        # 先找到根节点
        # TODO:[*]AttributeError: 'xml.etree.ElementTree.Element' object has no attribute 'getroot'
        root_node = self.base_msg.getroot()
        # 需要判断是否已经包含指定的node
        if singleton:
            if len(root_node.findall(node.key)) > 0:
                raise OSError
        # 创建需要直接插入的节点
        child = Element(node.key)
        child.text = node.val
        # 添加
        root_node.append(child)
        pass

    @property
    def message(self):
        return
