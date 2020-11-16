#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2017 cytopia <cytopia@everythingcli.org>

"""
vHost creator for Apache 2.2, Apache 2.4 and Nginx.
"""

############################################################
# Imports
############################################################

from __future__ import print_function

import getopt
import itertools
import os
import re
import sys
import time

import yaml

############################################################
# Globals
############################################################

# Default paths
CONFIG_PATH = "/etc/vhost-gen/conf.yml"
TEMPLATE_DIR = "/etc/vhost-gen/templates"

# stdout/stderr log paths
STDOUT_ACCESS = "/tmp/www-access.log"
STDERR_ERROR = "/tmp/www-error.log"

# Default configuration
DEFAULT_CONFIG = {
    "server": "nginx",
    "conf_dir": "/etc/nginx/conf.d",
    "custom": "",
    "vhost": {
        "port": "80",
        "ssl_port": "443",
        "name": {"prefix": "", "suffix": ""},
        "docroot": {"suffix": ""},
        "index": ["index.php", "index.html", "index.htm"],
        "ssl": {
            "http2": True,
            "dir_crt": "",
            "dir_key": "",
            "honor_cipher_order": "on",
            "ciphers": "HIGH:!aNULL:!MD5",
            "protocols": "TLSv1 TLSv1.1 TLSv1.2",
        },
        "log": {
            "access": {"prefix": "", "stdout": False},
            "error": {"prefix": "", "stderr": False},
            "dir": {"create": False, "path": "/var/log/nginx"},
        },
        "php_fpm": {"enable": False, "address": "", "port": 9000,
                    "timeout": 180},
        "alias": [],
        "deny": [],
        "server_status": {"enable": False, "alias": "/server-status"},
    },
}

# Available templates
TEMPLATES = {"apache22": "apache22.yml", "apache24": "apache24.yml",
             "nginx": "nginx.yml"}


############################################################
# System Functions
############################################################


def print_help():
    """Show program help."""
    print(
        """
    Usage: vhost-gen -p|r <str> -n <str> [-l <str> -c <str> -t <str> -o <str> -d -s -v]
       vhost-gen --help
       vhost-gen --version
    
    vhost-gen will dynamically generate vhost configuration files
    for Nginx, Apache 2.2 or Apache 2.4 depending on what you have set
    in /etc/vhost-gen/conf.yml
    
    Required arguments:
    -p|r <str>  You need to choose one of the mutually exclusive arguments.
              -p: Path to document root/
              -r: http(s)://Host:Port for reverse proxy.
              Depening on the choice, it will either generate a document serving
              vhost or a reverse proxy vhost.
              Note, when using -p, this can also have a suffix directory to be set
              in conf.yml
    -l <str>    Location path when using reverse proxy.
              Note, this is not required for normal document root server (-p)
    -n <str>    Name of vhost
              Note, this can also have a prefix and/or suffix to be set in conf.yml
    
    Optional arguments:
    -m <str>    Vhost generation mode. Possible values are:
              -m plain: Only generate http version (default)
              -m ssl:   Only generate https version
              -m both:  Generate http and https version
              -m redir: Generate https version and make http redirect to https
              -m let: Generate https version and make http redirect to https (Let's Encrypt)
    -c <str>    Path to global configuration file.
              If not set, the default location is /etc/vhost-gen/conf.yml
              If no config is found, a default is used with all features turned off.
    -t <str>    Path to global vhost template directory.
              If not set, the default location is /etc/vhost-gen/templates/
              If vhost template files are not found in this directory, the program will
              abort.
    -o <str>    Path to local vhost template directory.
              This is used as a secondary template directory and definitions found here
              will be merged with the ones found in the global template directory.
              Note, definitions in local vhost teplate directory take precedence over
              the ones found in the global template directory.
    -d          Make this vhost the default virtual host.
              Note, this will also change the server_name directive of nginx to '_'
              as well as discarding any prefix or suffix specified for the name.
              Apache does not have any specialities, the first vhost takes precedence.
    -s          If specified, the generated vhost will be saved in the location found in
              conf.yml. If not specified, vhost will be printed to stdout.
    -v          Be verbose.
    
    Misc arguments:
    --help      Show this help.
    --version   Show version.
    """
    )


def print_version():
    """Show program version."""
    print("vhost-gen v1.0.1 (2020-09-29)")
    print("cytopia <cytopia@everythingcli.org>")
    print("https://github.com/devilbox/vhost-gen")
    print("The MIT License (MIT)")


############################################################
# Wrapper Functions
############################################################


def str_replace(string, replacer):
    """Generic string replace."""

    # Replace all 'keys' with 'values'
    for key, val in replacer.items():
        string = string.replace(key, val)

    return string


def str_indent(text, amount, char=" "):
    """Indent every newline inside str by specified value."""
    padding = amount * char
    return "".join(padding + line for line in text.splitlines(True))


def to_str(string):
    """Dummy string retriever."""
    if string is None:
        return ""
    return str(string)


def load_yaml(path):
    """Wrapper to load yaml file safely."""

    try:
        with open(path, "r") as stream:
            try:
                data = yaml.safe_load(stream)
                if data is None:
                    data = dict()
                return (True, data, "")
            except yaml.YAMLError as err:
                return (False, dict(), str(err))
    except IOError:
        return (False, dict(), "File does not exist: " + path)


def merge_yaml(yaml1, yaml2):
    """Merge two yaml strings. The secondary takes precedence."""
    return dict(itertools.chain(yaml1.items(), yaml2.items()))


def symlink(src, dst, force=False):
    """
    Wrapper function to create a symlink with the addition of
    being able to overwrite an already existing file.
    """

    if os.path.isdir(dst):
        return (False, "[ERR] destination is a directory: " + dst)

    if force and os.path.exists(dst):
        try:
            os.remove(dst)
        except OSError as err:
            return (False, "[ERR] Cannot delete: " + dst + ": " + str(err))

    try:
        os.symlink(src, dst)
    except OSError as err:
        return (False, "[ERR] Cannot create link: " + str(err))

    return (True, None)


############################################################
# Argument Functions
############################################################


def parse_args(argv):
    """Parse command line arguments."""

    # Config location, can be overwritten with -c
    l_config_path = CONFIG_PATH
    l_template_dir = TEMPLATE_DIR
    o_template_dir = None
    save = None
    path = None
    name = None
    proxy = None
    mode = None
    location = None
    default = False
    verbose = False

    # Define command line options
    try:
        opts, argv = getopt.getopt(argv, "vm:c:p:r:l:n:t:o:ds",
                                   ["version", "help"])
    except getopt.GetoptError as err:
        print("[ERR]", str(err), file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(2)

    # Get command line options
    for opt, arg in opts:
        if opt == "--version":
            print_version()
            sys.exit()
        elif opt == "--help":
            print_help()
            sys.exit()
        # Verbose
        elif opt == "-v":
            verbose = True
        # Config file overwrite
        elif opt == "-c":
            l_config_path = arg
        # Vhost document root path
        elif opt == "-p":
            path = arg
        # Vhost reverse proxy (ADDR:PORT)
        elif opt == "-r":
            proxy = arg
        # Mode overwrite
        elif opt == "-m":
            mode = arg
        # Location for reverse proxy
        elif opt == "-l":
            location = arg
        # Vhost name
        elif opt == "-n":
            name = arg
        # Global template dir
        elif opt == "-t":
            l_template_dir = arg
        # Local template dir
        elif opt == "-o":
            o_template_dir = arg
        # Save?
        elif opt == "-d":
            default = True
        elif opt == "-s":
            save = True

    return (
        l_config_path,
        l_template_dir,
        o_template_dir,
        path,
        proxy,
        mode,
        location,
        name,
        default,
        save,
        verbose,
    )


def validate_args_req(name, docroot, proxy, mode, location):
    """Validate required arguments."""
    # Validate required command line options are set
    if docroot is None and proxy is None:
        print("[ERR] -p or -r is required", file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)
    if docroot is not None and proxy is not None:
        print("[ERR] -p and -r are mutually exclusive", file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)

    # Check proxy string
    if proxy is not None:
        if location is None:
            print("[ERR] When specifying -r, -l is also required.",
                  file=sys.stderr)
            sys.exit(1)

        # Regex: HOSTNAME/IP:PORT
        regex = re.compile("(^http(s)?://[-_.a-zA-Z0-9]+:[0-9]+$)",
                           re.IGNORECASE)
        if not regex.match(proxy):
            print(
                "[ERR] Invalid proxy argument string: '%s', should be: %s or %s."
                % (proxy, "http(s)://HOST:PORT", "http(s)://IP:PORT"),
                file=sys.stderr,
            )
            sys.exit(1)

        port = int(re.sub("^.*:", "", proxy))
        if port < 1 or port > 65535:
            print(
                "[ERR] Invalid reverse proxy port range: '%d', should between 1 and 65535" % (
                    port),
                file=sys.stderr,
            )
            sys.exit(1)

    # Check mode string
    if mode is not None:
        if mode not in ("plain", "ssl", "both", "redir", "let"):
            print(
                "[ERR] Invalid -m mode string: '%s', should be: %s, %s, %s %s or %s"
                % (mode, "plain", "ssl", "both", "redir", "let"),
                file=sys.stderr,
            )
            sys.exit(1)

    # Check normal server settings
    if docroot is not None:
        if location is not None:
            print("[WARN] -l is ignored when using normal vhost (-p)",
                  file=sys.stderr)

    if name is None:
        print("[ERR] -n is required", file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)

    regex = re.compile("(^[-_.a-zA-Z0-9]+$)", re.IGNORECASE)
    if not regex.match(name):
        print("[ERR] Invalid name:", name, file=sys.stderr)
        sys.exit(1)


def validate_args_opt(config_path, tpl_dir):
    """Validate optional arguments."""

    if not os.path.isfile(config_path):
        print("[WARN] Config file not found:", config_path, file=sys.stderr)

    if not os.path.isdir(tpl_dir):
        print("[ERR] Template path does not exist:", tpl_dir, file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)

    # Validate global templates
    tpl_file = os.path.join(tpl_dir, TEMPLATES["apache22"])
    if not os.path.isfile(tpl_file):
        print("[ERR] Apache 2.2 template file does not exist:", tpl_file,
              file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)

    tpl_file = os.path.join(tpl_dir, TEMPLATES["apache24"])
    if not os.path.isfile(tpl_file):
        print("[ERR] Apache 2.4 template file does not exist:", tpl_file,
              file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)

    tpl_file = os.path.join(tpl_dir, TEMPLATES["nginx"])
    if not os.path.isfile(tpl_file):
        print("[ERR] Nginx template file does not exist:", tpl_file,
              file=sys.stderr)
        print("Type --help for help", file=sys.stderr)
        sys.exit(1)


############################################################
# Config File Functions
############################################################


def validate_config(config):
    """Validate some important keys in config dict."""

    # Validate server type
    valid_hosts = list(TEMPLATES.keys())
    if config["server"] not in valid_hosts:
        print("[ERR] httpd.server must be 'apache22', 'apache24' or 'nginx'",
              file=sys.stderr)
        print("[ERR] Your configuration is:", config["server"], file=sys.stderr)
        sys.exit(1)


#    # Validate if log dir can be created
#    log_dir = config['vhost']['log']['dir']['path']
#    if config['vhost']['log']['dir']['create']:
#        if not os.path.isdir(log_dir):
#            if not os.access(os.path.dirname(log_dir), os.W_OK):
#                print('[ERR] log directory does not exist and cannot be created:', log_dir,
#                      file=sys.stderr)
#                sys.exit(1)


############################################################
# Get vHost Skeleton placeholders
############################################################


def vhost_get_port(config, ssl):
    """Get listen port."""
    if ssl:
        if config["server"] == "nginx":
            return to_str(config["vhost"]["ssl_port"]) + " ssl"
        return to_str(config["vhost"]["ssl_port"])

    return to_str(config["vhost"]["port"])


def vhost_get_http_proto(config, ssl):
    """Get HTTP protocol. Only relevant for Apache 2.4/Nginx and SSL."""

    if config["server"] == "apache24":
        if ssl and config["vhost"]["ssl"]["http2"]:
            return "h2 http/1.1"
        return "http/1.1"

    if config["server"] == "nginx":
        if ssl and config["vhost"]["ssl"]["http2"]:
            return " http2"

    return ""


def vhost_get_default_server(config, default):
    """
    Get vhost default directive which makes it the default vhost.

    :param dict config: Configuration dictionary
    :param bool default: Default vhost
    """
    if default:
        if config["server"] == "nginx":
            # The leading space is required here for the template to
            # separate it from the port directive left to it.
            return " default_server"

        if config["server"] in ("apache22", "apache24"):
            return "_default_"

    else:
        if config["server"] in ("apache22", "apache24"):
            return "*"

    return ""


def vhost_get_server_name(config, server_name, default):
    """Get server name."""

    # Nginx uses: "server_name _;" as the default
    if default and config["server"] == "nginx":
        return "_"

    # Apache does not have any specialities. The first one takes precedence.
    # The name will be the same as with every other vhost.
    prefix = to_str(config["vhost"]["name"]["prefix"])
    suffix = to_str(config["vhost"]["name"]["suffix"])
    return prefix + server_name + suffix


def vhost_get_access_log(config, server_name):
    """Get access log directive."""
    if config["vhost"]["log"]["access"]["stdout"]:
        return STDOUT_ACCESS

    prefix = to_str(config["vhost"]["log"]["access"]["prefix"])
    name = prefix + server_name + "-access.log"
    path = os.path.join(config["vhost"]["log"]["dir"]["path"], name)
    return path


def vhost_get_error_log(config, server_name):
    """Get error log directive."""
    if config["vhost"]["log"]["error"]["stderr"]:
        return STDERR_ERROR

    prefix = to_str(config["vhost"]["log"]["error"]["prefix"])
    name = prefix + server_name + "-error.log"
    path = os.path.join(config["vhost"]["log"]["dir"]["path"], name)
    return path


############################################################
# Get vHost Type (normal or reverse proxy
############################################################


def vhost_get_vhost_docroot(config, template, docroot, proxy):
    """Get document root directive."""
    if proxy is not None:
        return ""

    return str_replace(
        template["vhost_type"]["docroot"],
        {
            "__DOCUMENT_ROOT__": vhost_get_docroot_path(config, docroot, proxy),
            "__INDEX__": vhost_get_index(config),
        },
    )


def vhost_get_vhost_rproxy(template, proxy, location):
    """Get reverse proxy definition."""
    if proxy is not None:
        return str_replace(
            template["vhost_type"]["rproxy"],
            {
                "__LOCATION__": location,
                "__PROXY_PROTO__": re.sub("://.*$", "", proxy),
                "__PROXY_ADDR__": re.search("^.*://(.+):[0-9]+", proxy).group(
                    1),
                "__PROXY_PORT__": re.sub("^.*:", "", proxy),
            },
        )
    return ""


############################################################
# Get vHost Features
############################################################


def vhost_get_vhost_ssl(config, template, server_name, let):
    """Get ssl definition."""
    return str_replace(
        template["features"]["ssl"],
        {
            "__SSL_PATH_CRT__": to_str(
                vhost_get_ssl_crt_path(config, server_name, let)),
            "__SSL_PATH_KEY__": to_str(
                vhost_get_ssl_key_path(config, server_name, let)),
            "__SSL_PROTOCOLS__": to_str(config["vhost"]["ssl"]["protocols"]),
            "__SSL_HONOR_CIPHER_ORDER__": to_str(
                config["vhost"]["ssl"]["honor_cipher_order"]),
            "__SSL_CIPHERS__": to_str(config["vhost"]["ssl"]["ciphers"]),
        },
    )


def vhost_get_vhost_redir(config, template, server_name):
    """Get redirect to ssl definition."""
    return str_replace(
        template["features"]["redirect"],
        {
            "__VHOST_NAME__": vhost_get_server_name(config, server_name, 0),
            "__SSL_PORT__": to_str(config["vhost"]["ssl_port"]),
        },
    )


def vhost_get_ssl_crt_path(config, server_name, let):
    """Get ssl crt path"""

    prefix = to_str(config["vhost"]["name"]["prefix"])
    suffix = to_str(config["vhost"]["name"]["suffix"])
    name = prefix + server_name + suffix
    if let:
        name = os.path.join(name, "fullchain.pem")
    else:
        name += ".crt"

    path = to_str(config["vhost"]["ssl"]["dir_crt"])
    return os.path.join(path, name)


def vhost_get_ssl_key_path(config, server_name, let):
    """Get ssl key path"""
    prefix = to_str(config["vhost"]["name"]["prefix"])
    suffix = to_str(config["vhost"]["name"]["suffix"])
    name = prefix + server_name + suffix
    if let:
        name = os.path.join(name, "privkey.pem")
    else:
        name += ".key"

    path = to_str(config["vhost"]["ssl"]["dir_crt"])
    return os.path.join(path, name)


def vhost_get_docroot_path(config, docroot, proxy):
    """Get path of document root."""
    if proxy is not None:
        return ""

    suffix = to_str(config["vhost"]["docroot"]["suffix"])
    path = os.path.join(docroot, suffix)
    return path


def vhost_get_index(config):
    """Get index."""
    if "index" in config["vhost"] and config["vhost"]["index"]:
        elem = config["vhost"]["index"]
    else:
        elem = DEFAULT_CONFIG["vhost"]["index"]

    return " ".join(elem)


def vhost_get_php_fpm(config, template, docroot, proxy):
    """Get PHP FPM directive. If using reverse proxy, PHP-FPM will be disabled."""
    if proxy is not None:
        return ""

    # Get PHP-FPM
    php_fpm = ""
    if config["vhost"]["php_fpm"]["enable"]:
        php_fpm = str_replace(
            template["features"]["php_fpm"],
            {
                "__PHP_ADDR__": to_str(config["vhost"]["php_fpm"]["address"]),
                "__PHP_PORT__": to_str(config["vhost"]["php_fpm"]["port"]),
                "__PHP_TIMEOUT__": to_str(
                    config["vhost"]["php_fpm"]["timeout"]),
                "__DOCUMENT_ROOT__": vhost_get_docroot_path(config, docroot,
                                                            proxy),
            },
        )
    return php_fpm


def vhost_get_aliases(config, template):
    """Get virtual host alias directives."""
    aliases = []
    for item in config["vhost"]["alias"]:
        # Add optional xdomain request if enabled
        xdomain_request = ""
        if "xdomain_request" in item:
            if item["xdomain_request"]["enable"]:
                xdomain_request = str_replace(
                    template["features"]["xdomain_request"],
                    {"__REGEX__": to_str(item["xdomain_request"]["origin"])},
                )
        # Replace everything
        aliases.append(
            str_replace(
                template["features"]["alias"],
                {
                    "__ALIAS__": to_str(item["alias"]),
                    "__PATH__": to_str(item["path"]),
                    "__XDOMAIN_REQ__": str_indent(xdomain_request, 4).rstrip(),
                },
            )
        )
    # Join by OS independent newlines
    return os.linesep.join(aliases)


def vhost_get_denies(config, template):
    """Get virtual host deny alias directives."""
    denies = []
    for item in config["vhost"]["deny"]:
        denies.append(
            str_replace(template["features"]["deny"],
                        {"__REGEX__": to_str(item["alias"])})
        )
    # Join by OS independent newlines
    return os.linesep.join(denies)


def vhost_get_server_status(config, template):
    """Get virtual host server status directivs."""
    status = ""
    if config["vhost"]["server_status"]["enable"]:
        status = template["features"]["server_status"]

    return str_replace(status, {
        "__REGEX__": to_str(config["vhost"]["server_status"]["alias"])})


def vhost_get_custom_section(config):
    """Get virtual host custom directives."""
    return to_str(config["custom"])


############################################################
# vHost create
############################################################


def get_vhost_plain(config, tpl, docroot, proxy, location, server_name,
    default):
    """Get plain vhost"""
    return str_replace(
        tpl["vhost"],
        {
            "__PORT__": vhost_get_port(config, False),
            "__HTTP_PROTO__": vhost_get_http_proto(config, False),
            "__DEFAULT_VHOST__": vhost_get_default_server(config, default),
            "__DOCUMENT_ROOT__": vhost_get_docroot_path(config, docroot, proxy),
            "__VHOST_NAME__": vhost_get_server_name(config, server_name,
                                                    default),
            "__VHOST_DOCROOT__": str_indent(
                vhost_get_vhost_docroot(config, tpl, docroot, proxy), 4
            ),
            "__VHOST_RPROXY__": str_indent(
                vhost_get_vhost_rproxy(tpl, proxy, location), 4),
            "__REDIRECT__": "",
            "__SSL__": "",
            "__INDEX__": vhost_get_index(config),
            "__ACCESS_LOG__": vhost_get_access_log(config, server_name),
            "__ERROR_LOG__": vhost_get_error_log(config, server_name),
            "__PHP_FPM__": str_indent(
                vhost_get_php_fpm(config, tpl, docroot, proxy),
                4),
            "__ALIASES__": str_indent(vhost_get_aliases(config, tpl), 4),
            "__DENIES__": str_indent(vhost_get_denies(config, tpl), 4),
            "__SERVER_STATUS__": str_indent(
                vhost_get_server_status(config, tpl), 4),
            "__CUSTOM__": str_indent(vhost_get_custom_section(config), 4),
        },
    )


def get_vhost_ssl(config, tpl, docroot, proxy, location, server_name, default,
    let=False):
    """Get ssl vhost"""
    return str_replace(
        tpl["vhost"],
        {
            "__PORT__": vhost_get_port(config, True),
            "__HTTP_PROTO__": vhost_get_http_proto(config, True),
            "__DEFAULT_VHOST__": vhost_get_default_server(config, default),
            "__DOCUMENT_ROOT__": vhost_get_docroot_path(config, docroot, proxy),
            "__VHOST_NAME__": vhost_get_server_name(config, server_name,
                                                    default),
            "__VHOST_DOCROOT__": str_indent(
                vhost_get_vhost_docroot(config, tpl, docroot, proxy), 4
            ),
            "__VHOST_RPROXY__": str_indent(
                vhost_get_vhost_rproxy(tpl, proxy, location), 4),
            "__REDIRECT__": "",
            "__SSL__": str_indent(
                vhost_get_vhost_ssl(config, tpl, server_name, let),
                4),
            "__INDEX__": vhost_get_index(config),
            "__ACCESS_LOG__": vhost_get_access_log(config,
                                                   server_name + "_ssl"),
            "__ERROR_LOG__": vhost_get_error_log(config, server_name + "_ssl"),
            "__PHP_FPM__": str_indent(
                vhost_get_php_fpm(config, tpl, docroot, proxy),
                4),
            "__ALIASES__": str_indent(vhost_get_aliases(config, tpl), 4),
            "__DENIES__": str_indent(vhost_get_denies(config, tpl), 4),
            "__SERVER_STATUS__": str_indent(
                vhost_get_server_status(config, tpl), 4),
            "__CUSTOM__": str_indent(vhost_get_custom_section(config), 4),
        },
    )


def get_vhost_redir(config, tpl, docroot, proxy, server_name, default):
    """Get redirect to ssl vhost"""
    return str_replace(
        tpl["vhost"],
        {
            "__PORT__": vhost_get_port(config, False),
            "__HTTP_PROTO__": vhost_get_http_proto(config, False),
            "__DEFAULT_VHOST__": vhost_get_default_server(config, default),
            "__DOCUMENT_ROOT__": vhost_get_docroot_path(config, docroot, proxy),
            "__VHOST_NAME__": vhost_get_server_name(config, server_name,
                                                    default),
            "__VHOST_DOCROOT__": "",
            "__VHOST_RPROXY__": "",
            "__REDIRECT__": str_indent(
                vhost_get_vhost_redir(config, tpl, server_name), 4),
            "__SSL__": "",
            "__INDEX__": "",
            "__ACCESS_LOG__": vhost_get_access_log(config, server_name),
            "__ERROR_LOG__": vhost_get_error_log(config, server_name),
            "__PHP_FPM__": "",
            "__ALIASES__": "",
            "__DENIES__": "",
            "__SERVER_STATUS__": "",
            "__CUSTOM__": "",
        },
    )


def get_vhost(config, tpl, docroot, proxy, mode, location, server_name,
    default):
    """Create the vhost."""

    if mode == "ssl":
        return get_vhost_ssl(config, tpl, docroot, proxy, location, server_name,
                             default)
    if mode == "both":
        return get_vhost_ssl(
            config, tpl, docroot, proxy, location, server_name, default
        ) + get_vhost_plain(config, tpl, docroot, proxy, location, server_name,
                            default)

    if mode == "redir":
        return get_vhost_ssl(
            config, tpl, docroot, proxy, location, server_name, default
        ) + get_vhost_redir(config, tpl, docroot, proxy, server_name, default)

    if mode == "let":
        return get_vhost_ssl(
            config, tpl, docroot, proxy, location, server_name, default, True
        ) + get_vhost_redir(config, tpl, docroot, proxy, server_name, default)

    return get_vhost_plain(config, tpl, docroot, proxy, location, server_name,
                           default)


############################################################
# Load configs and templates
############################################################


def load_config(config_path):
    """Load config and merge with defaults in case not found or something is missing."""

    # Load configuration file
    if os.path.isfile(config_path):
        succ, config, err = load_yaml(config_path)
        if not succ:
            return (False, dict(), err)
    else:
        print("[WARN] config file not found", config_path, file=sys.stderr)
        config = dict()

    # Merge config settings with program defaults (config takes precedence over defaults)
    config = merge_yaml(DEFAULT_CONFIG, config)

    return (True, config, "")


def load_template(template_dir, o_template_dir, server):
    """Load global and optional template file and merge them."""

    # Load global template file
    succ, template, err = load_yaml(
        os.path.join(template_dir, TEMPLATES[server]))
    if not succ:
        return (
            False,
            dict(),
            "(global template: " + os.path.join(template_dir,
                                                TEMPLATES[
                                                    server]) + "): " + err,
        )

    # Load optional template file (if specified file and merge it)
    if o_template_dir is not None:
        # Template dir exists, but no file was added, give the user a warning, but do not abort
        if not os.path.isfile(os.path.join(o_template_dir, TEMPLATES[server])):
            print(
                "[WARN] override template not found: ",
                os.path.join(o_template_dir, TEMPLATES[server]),
                file=sys.stderr,
            )
        else:
            succ, template2, err = load_yaml(
                os.path.join(o_template_dir, TEMPLATES[server]))
            if not succ:
                return (
                    False,
                    dict(),
                    "(override template: "
                    + os.path.join(o_template_dir, TEMPLATES[server])
                    + "): "
                    + err,
                )
            template = merge_yaml(template, template2)

    return (True, template, "")


############################################################
# Post actions
############################################################


def apply_log_settings(config):
    """
    This function will apply various settings for the log defines, including
    creating the directory itself as well as handling log file output (access
    and error) to stderr/stdout.
    """
    # Symlink stdout to access logfile
    if config["vhost"]["log"]["access"]["stdout"]:
        succ, err = symlink("/dev/stdout", STDOUT_ACCESS, force=True)
        if not succ:
            return (False, err)

    # Symlink stderr to error logfile
    if config["vhost"]["log"]["error"]["stderr"]:
        succ, err = symlink("/dev/stderr", STDERR_ERROR, force=True)
        if not succ:
            return (False, err)

    # Create log dir
    if config["vhost"]["log"]["dir"]["create"]:
        if not os.path.isdir(config["vhost"]["log"]["dir"]["path"]):
            try:
                os.makedirs(config["vhost"]["log"]["dir"]["path"])
            except OSError as err:
                return (False, "[ERR] Cannot create directory: " + str(err))

    return (True, None)


############################################################
# Main Function
############################################################


def main(argv):
    """Main entrypoint."""

    # Get command line arguments
    (
        config_path,
        tpl_dir,
        o_tpl_dir,
        docroot,
        proxy,
        mode,
        location,
        name,
        default,
        save,
        verbose,
    ) = parse_args(argv)

    # Validate command line arguments This will abort the program on error
    # This will abort the program on error
    validate_args_req(name, docroot, proxy, mode, location)
    validate_args_opt(config_path, tpl_dir)

    # Load config
    succ, config, err = load_config(config_path)
    if not succ:
        print("[ERR] Error loading config", err, file=sys.stderr)
        sys.exit(1)

    # Load template
    succ, template, err = load_template(tpl_dir, o_tpl_dir, config["server"])
    if not succ:
        print("[ERR] Error loading template", err, file=sys.stderr)
        sys.exit(1)

    # Validate configuration file
    # This will abort the program on error
    validate_config(config)

    # Retrieve fully build vhost
    vhost = get_vhost(config, template, docroot, proxy, mode, location, name,
                      default)

    if verbose:
        print(
            "vhostgen: [%s] Adding: %s"
            % (
                time.strftime("%Y-%m-%d %H:%M:%S"),
                to_str(config["vhost"]["name"]["prefix"])
                + name
                + to_str(config["vhost"]["name"]["suffix"]),
            )
        )

    if save:
        if not os.path.isdir(config["conf_dir"]):
            print("[ERR] output conf_dir does not exist:", config["conf_dir"],
                  file=sys.stderr)
            sys.exit(1)
        if not os.access(config["conf_dir"], os.W_OK):
            print(
                "[ERR] directory does not have write permissions",
                config["conf_dir"],
                file=sys.stderr,
            )
            sys.exit(1)

        vhost_path = os.path.join(config["conf_dir"], name + ".conf")
        with open(vhost_path, "w") as outfile:
            outfile.write(vhost)

        # Apply settings for logging (symlinks, mkdir) only in save mode
        succ, err = apply_log_settings(config)
        if not succ:
            print(err, file=sys.stderr)
            sys.exit(1)
    else:
        print(vhost)


############################################################
# Main Entry Point
############################################################

if __name__ == "__main__":
    main(sys.argv[1:])
