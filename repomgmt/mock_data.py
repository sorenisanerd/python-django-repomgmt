#
#   Copyright 2012 Cisco Systems, Inc.
#
#   Author: Soren Hansen <sorhanse@cisco.com>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
import textwrap

packages = [('folsom-proposed', 'main', 'i386', 'cinder-api', '2012.2.1~+cisco-folsom1260-53'),
            ('folsom-proposed', 'main', 'i386', 'cinder-common', '2012.2.1~+cisco-folsom1260-53'),
            ('folsom-proposed', 'main', 'amd64', 'cinder-api', '2012.2.1~+cisco-folsom1260-53'),
            ('folsom-proposed', 'main', 'amd64', 'cinder-common', '2012.2.1~+cisco-folsom1260-53'),
            ('folsom-proposed', 'main', 'source', 'cinder', '2012.2.1~+cisco-folsom1260-53')]

chroots = ['cisco-folsom-i386',
           'cisco-folsom-amd64']


def run_cmd(cmd, input=None):
    global chroots
    if cmd[0] == 'sbuild-update':
        return ''
    if cmd[0] == 'gpg':
        if cmd[1] == '--batch' and cmd[2] == '--gen-key':
            return 'gpg: key D58FDBBA marked as ultimately trusted'
        elif cmd[1:5] == ['-a', '--export-options', 'export-clean', '--export']:
            return textwrap.dedent('''\
               -----BEGIN PGP PUBLIC KEY BLOCK-----
               Version: GnuPG v1.4.12 (GNU/Linux)
               
               mQINBFFMZjUBEADLDDUf3ERgeHUZXSJVlPEVRbciqinEiQInflL1Lcg+5AkPtFzt
               dImXFHds9hI20zwCMcRc0xD3G8ufd8feGSqxZMiZmVClY2m06Dd2nq3EYVEo/qx1
               I4LtubvLiWwddUgPHEYoQXvD3Q==
               =/Xyq
               -----END PGP PUBLIC KEY BLOCK-----
               ''')


    if cmd[0] == 'sudo' and cmd[1] == 'sed':
        return ''
    if cmd[0] == 'schroot':
        if cmd[1] == '-l':
            out = ''
            for chroot in chroots:
                out += 'source:%s\n' % (chroot,)
            return out
        else:
            chroot = None
            user = None
            idx = 1
            while idx < len(cmd):
                if cmd[idx].startswith('-c'):
                    chroot = cmd[idx+1]
                    idx += 2
                elif cmd[idx].startswith('-u'):
                    user = cmd[idx+1]
                    idx += 2
                elif cmd[idx] == '--':
                    if chroot is not None and user is not None:
                        return ''
    if cmd[0] == 'mk-sbuild':
        idx = 1
        name = None
        arch = None
        distro = None
        while idx < len(cmd):
            if cmd[idx].startswith('--name='):
                name = cmd[idx][len('--name=')]
                idx += 1
            elif cmd[idx].startswith('--arch='):
                arch = cmd[idx][len('--arch=')]
                idx += 1
            elif cmd[idx].startswith('--type='):
                type = cmd[idx][len('--type=')]
                idx += 1
            elif distro is None:
                distro = cmd[idx]
                idx += 1
            else:
                break
        chroots += ['%s-%s' % (name, arch)]
        return ''
    if cmd[0] == 'reprepro':
        idx = 1
        subcmd = None
        arch = None
        distro = None
        while idx < len(cmd):
            if cmd[idx] == '-b':
                idx += 2
                continue
            elif cmd[idx] == '-A':
                arch = cmd[idx+1]
                idx += 2
                continue
            elif subcmd is None:
                subcmd = cmd[idx]
                idx += 1
            elif subcmd is not None:
                if distro is None:
                    distro = cmd[idx]
                idx += 1
            else:
                raise Exception('Argh')
        if subcmd == 'list':
            out = ''
            global packages
            for (d, s, a, p, v) in packages:
                if distro and d != distro:
                    continue
                if arch and a != arch:
                    continue
                out += '%s|%s|%s: %s %s\n' % (d, s, a, p, v)
            return out
        elif subcmd == 'export':
            return ''
        elif subcmd == 'pull':
            target = distro
            if distro.endswith('-proposed'):
                source = distro[:-len('-proposed')]
                source += '-staged'
            else:
                source = '%s-proposed' % (distro,)
            pkgs = {}
            for pkg_info in packages:
                distro, section, arch, pkg, version = pkg_info
                if distro == source:
                    pkgs[pkg] = pkg_info
            new_packages = []
            for pkg_info in packages:
                distro, section, arch, pkg, version = pkg_info
                if distro == target and pkg in pkgs:
                    new_pkg_info = pkgs.pop(pkg)
                    _distro, section, arch, pkg, version = new_pkg_info
                    new_packages += [(target, section, arch, pkg, version)]
                else:
                    new_packages += [pkg_info]
            for pkg in pkgs:
                new_pkg_info = pkgs[pkg]
                _distro, section, arch, pkg, version = new_pkg_info
                new_packages += [(target, section, arch, pkg, version)]
            packages = new_packages
            return ''

    raise Exception('Missing mock data for %r' % (cmd,))

