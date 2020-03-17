import unittest
from support import coverageview_xml
from xml.etree.ElementTree import TreeBuilder

class SupportTest(unittest.TestCase):
    def test_coverage_xml():
        builder=TreeBuilder()
        dict_coverage=dict(
            coverageview=dict(
                coveragebands=dict(
                    band1=dict(
                        definition='ceshi',
                        index=1
                    )
                )
            )
        )
        coverageview_xml(builder,dict_coverage)

def main():
    SupportTest().test_coverage_xml()

if __name__ == '__main__':
    main()