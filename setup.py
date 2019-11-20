from setuptools import setup

setup(name='datamijn',
      version='0.1',
      description='Awesome declarative binary parser',
      url='',
      author='Sanqui',
      author_email='me@sanqui.net',
#      license='MIT',
      packages=['datamijn'],
      include_package_data=True,
      install_requires=[
        'lark-parser',
        'construct',
        'pypng',
        'oyaml'
        'click',
        'urwid',
      ],
      zip_safe=False)
