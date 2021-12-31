from OpenSSL import SSL
from cryptography import x509
from cryptography.x509.oid import NameOID
import idna
from collections import namedtuple
# noinspection PyPackageRequirements
import socks  # pysocks

HostInfo = namedtuple(field_names='cert hostname peername', typename='HostInfo')


class HttpDomainCertificateInfo(dict):
    def __init__(self, host_name: str, port: int, proxy_ip='', proxy_port=8080):
        super().__init__()
        self.hostinfo = self.get_certificate(host_name, port, proxy_ip, proxy_port)
        self.update({
            'hostname': self.hostinfo.hostname,
            'peer_name': self.hostinfo.peername,
            'common_name': self.get_common_name(),
            'SAN': self.get_alt_names(),
            'issuer': self.get_issuer(),
            'not_before': self.hostinfo.cert.not_valid_before,
            'not_after': self.hostinfo.cert.not_valid_after
        })

    @staticmethod
    def get_certificate(host_name, port, proxy_ip='', proxy_port=8080):
        sock = socks.socksocket()  # Same API as socket.socket in the standard lib
        if proxy_ip:
            sock.set_proxy(socks.HTTP, proxy_ip, proxy_port)

        hostname_idna = idna.encode(host_name)
        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # sock = socket.socket()

        sock.connect((host_name, port))
        peer_name = sock.getpeername()
        ctx = SSL.Context(SSL.SSLv23_METHOD)  # most compatible
        ctx.check_hostname = False
        ctx.verify_mode = SSL.VERIFY_NONE

        sock_ssl = SSL.Connection(ctx, sock)
        sock_ssl.set_connect_state()
        sock_ssl.set_tlsext_host_name(hostname_idna)
        sock_ssl.do_handshake()
        cert = sock_ssl.get_peer_certificate()
        crypto_cert = cert.to_cryptography()
        sock_ssl.close()
        sock.close()

        return HostInfo(cert=crypto_cert, peername=peer_name, hostname=host_name)

    def get_alt_names(self):
        try:
            ext = self.hostinfo.cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            return ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            return None

    def get_common_name(self):
        try:
            names = self.hostinfo.cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            return names[0].value
        except x509.ExtensionNotFound:
            return None

    def get_issuer(self):
        try:
            names = self.hostinfo.cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
            return names[0].value
        except x509.ExtensionNotFound:
            return None

    def get_basic_info(self):
        s = '''» {hostname} « … {peername}
        \tcommonName: {commonname}
        \tSAN: {SAN}
        \tissuer: {issuer}
        \tnotBefore: {notbefore}
        \tnotAfter:  {notafter}
        '''.format(
            hostname=self.hostinfo.hostname,
            peername=self.hostinfo.peername,
            commonname=self.get_common_name(),
            SAN=self.get_alt_names(),
            issuer=self.get_issuer(),
            notbefore=self.hostinfo.cert.not_valid_before,
            notafter=self.hostinfo.cert.not_valid_after
        )
        return s
