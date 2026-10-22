# PyInstaller spec for Room.app. Run through build.sh, which makes the icons first.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
ICONS = os.path.join(ROOT, 'build', 'icons')
VERSION = os.environ.get('ROOM_VERSION', '1.0.0')

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'web'), 'web'),
           (os.path.join(ICONS, 'menubar.png'), '.'),
           (os.path.join(ICONS, 'menubar@2x.png'), '.')],
    # Imported inside functions, or only by the server thread.
    hiddenimports=['server', 'sources', 'dig', 'tv', 'room', 'settings', 'engine', 'paths',
                   'samsungtvws', 'qrcode', 'certifi'],
    # The C speedups in these ship arm64-only wheels; each falls back to pure Python without them.
    excludes=['tkinter', 'PIL', 'pytest', 'multidict._multidict', 'multidict._testcapi',
              'yarl._quoting_c', 'propcache._helpers_c'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Room', console=False,
          target_arch=os.environ.get('ROOM_ARCH', 'universal2'),
          codesign_identity=os.environ.get('ROOM_SIGN_ID') or None,
          entitlements_file=os.path.join(SPECPATH, 'entitlements.plist'))
coll = COLLECT(exe, a.binaries, a.datas, name='Room')
app = BUNDLE(
    coll,
    name='Room.app',
    icon=os.path.join(ICONS, 'Room.icns'),
    bundle_identifier='com.aniekank.room',
    version=VERSION,
    info_plist={
        'CFBundleDisplayName': 'Room',
        'CFBundleShortVersionString': VERSION,
        'LSUIElement': True,  # menu bar only, no Dock icon
        'LSMinimumSystemVersion': '11.0',
        'NSHumanReadableCopyright': 'Personal use. https://github.com/aniekank/room',
        'NSLocalNetworkUsageDescription': 'Room finds your Samsung TV on your Wi-Fi and serves its channels to the TV and your phone.',
        'NSAppleEventsUsageDescription': 'Room shows a notification when it is time for Keys.',
    },
)
