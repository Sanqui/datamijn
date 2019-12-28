from setuptools import setup

setup(name='datamijn',
      version='0.4.3',
      description='Awesome declarative binary data parser',
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
        'oyaml',
        'click',
        'urwid',
      ],
      zip_safe=False)
