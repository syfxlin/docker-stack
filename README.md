# docker-stack

> 基于 Docker 的个人服务器一键环境。

![License](https://img.shields.io/github/license/syfxlin/docker-stack.svg?style=flat-square) ![Author](https://img.shields.io/badge/Author-Otstar%20Lin-blue.svg?style=flat-square)

## 使用方法 Usage

### DNMP

本项目的 DNMP 包含了以下容器：

- Nginx：负责反向代理所有容器站点，也可以运行静态站点，按需求配置
- Apache：负责运行静态和 PHP 站点
- PHP-FPM：负责运行 PHP 程序，同时支持运行 Swoole。
- MySQL & PostgreSQL：数据库

容器中服务的配置都存储于 `service` 文件夹中，数据都存储于 `data` 文件夹中，日志都存储于 `logs` 下，`web/wwwroot` 为网站目录，`share` 为所有容器中的共享目录，如果有需要在各容器中或宿主机中共享文件或文件夹，可以存储于该文件夹。

#### 启动

1. 先修改下 `bin/dnmp` 脚本内的 `DNMP_DIR` 变量为你的 dnmp 目录。
2. 然后在 dnmp 下运行 `docker-compose up -d` 或者运行 `bin/dnmp up` 即可完成启动。

#### 配置

Apache 和 Nginx 配置使用 [devilbox/vhost-gen](https://github.com/devilbox/vhost-gen)，具体命令见下方：

- 创建静态站点（Nginx，HttpOnly）

```shell script
bin/nginx-vg -p /data/wwwroot/<you_host> -n <you_host> -s
docker restart nginx
```

- 创建 PHP 站点（Apache，HttpOnly）

```shell script
bin/apache-vg -p /data/wwwroot/<you_host> -n <you_host> -s
bin/nginx-vg -r http://apache:80 -l / -s
docker restart apache
docker restart nginx
```

- 创建 Https 站点（Nginx，Https）

```shell script
# 先创建一个临时的 Http 站点用于申请 ssl 证书
bin/nginx-vg -p /data/wwwroot/<you_host> -n <you_host> -s
docker restart nginx
# 申请 ssl 证书
bin/certbot certonly --nginx
# 将站点升级为 Https
bin/nginx-vg -p /data/wwwroot/<you_host> -n <you_host> -s -m let
docker restart nginx
```

- 创建 Http 站点（Apache，Https）

```shell script
# 先创建一个临时的 Http 站点用于申请 ssl 证书
bin/nginx-vg -p /data/wwwroot/<you_host> -n <you_host> -s
docker restart nginx
# 申请 ssl 证书
bin/certbot certonly --nginx
# 创建 Apache 站点
bin/apache-vg -p /data/wwwroot/<you_host> -n <you_host> -s -m let
# 将 Nginx 反代升级为 Https
bin/nginx-vg -r https://apache:443 -s -m let
docker restart apache
docker restart nginx
```

数据库密码，各种服务的版本，PHP 插件等配置修改 `.env` 文件中的环境变量即可。

#### 后续增加服务

DNMP 启动后，我们可以很方便的添加额外的服务到 DNMP 网络中。在 `apps` 下一个 Portainer Docker 管理面板的案例，你可以参考该样例进行后续服务的添加。

```yaml
# 请注意为所有需要加入 DNMP 网络的 docker-compose.yml 文件中都加入这些配置
networks:
  default:
    external:
      name: dnmp
```

额外的容器启动后，我们可以到 NPM 中配置反向代理即可完成服务的添加。

## 维护者 Maintainer

docker-stack 由 [Otstar Lin](https://ixk.me/) 和下列 [贡献者](https://github.com/syfxlin/docker-stack/graphs/contributors) 的帮助下撰写和维护。

> Otstar Lin - [Personal Website](https://ixk.me/) · [Blog](https://blog.ixk.me/) · [Github](https://github.com/syfxlin)

## 许可证 License

![License](https://img.shields.io/github/license/syfxlin/docker-stack.svg?style=flat-square)

根据 MIT License 许可证开源。
