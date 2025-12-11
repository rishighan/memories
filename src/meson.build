pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'memories'

gnome = import('gnome')

gnome.compile_resources('memories',
  'memories.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: files('window.ui', 'style.css', 'resources/shortcuts-dialog.ui'),
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'memories.in',
  output: 'memories',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

# Install main Python files
install_data(
  '__init__.py',
  'main.py',
  'window.py',
  install_dir: moduledir,
  preserve_path: true
)

# Install subdirectories with all their files
install_subdir('api', install_dir: moduledir, strip_directory: false)
install_subdir('ui', install_dir: moduledir, strip_directory: false)
install_subdir('utils', install_dir: moduledir, strip_directory: false)