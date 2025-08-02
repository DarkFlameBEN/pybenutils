DeprecationWarning("This module path is deprecated. Use pybenproxmox module directly instead")
try:
    from pybenproxmox import ProxmoxCls as Proxmox
except ImportError:
    from pybenutils.useful import install_pip_package_using_pip
    install_pip_package_using_pip('pybenproxmox')
    from pybenproxmox import ProxmoxCls as Proxmox
