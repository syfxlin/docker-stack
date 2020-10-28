# docker-stack

> 基于 Docker 的个人服务器一键环境。

![License](https://img.shields.io/github/license/syfxlin/docker-stack.svg?style=flat-square) ![Author](https://img.shields.io/badge/Author-Otstar%20Lin-blue.svg?style=flat-square)

## 使用方法 Usage

### DNMP

本项目的 DNMP 包含了以下容器：

- Nginx：负责反向代理所有容器站点
- Apache：负责运行静态和 PHP 站点
- PHP-FPM：负责运行 PHP 程序，同时支持运行 Swoole。
- MySQL & PostgreSQL：数据库

容器中服务的配置都存储于 `service` 文件夹中，数据都存储于 `data` 文件夹中，日志大部分都存储于 `logs` 和 `web/wwwlogs` 下，`web/wwwroot` 为网站目录，`share` 为所有容器中的共享目录，如果有需要在各容器中或宿主机中共享文件或文件夹，可以存储于该文件夹。

#### 启动

1. 先修改下 `bin/dnmp` 脚本内的 `DNMP_DIR` 变量为你的 dnmp 目录。
2. 然后在 dnmp 下运行 `docker-compose up -d` 或者运行 `bin/dnmp up` 即可完成启动。

#### 配置

Nginx 反向代理使用的是 [jc21/nginx-proxy-manager](https://github.com/jc21/nginx-proxy-manager)，打开 `http://<you_host>:81` 进入 NPM 面板进行配置。具体请查阅 [jc21/nginx-proxy-manager](https://github.com/jc21/nginx-proxy-manager) 相关文档。

Apache 配置使用 [devilbox/vhost-gen](https://github.com/devilbox/vhost-gen)，具体命令见下方：

1. 创建 Http Only 站点
```shell script
bin/vhost-gen -p /data/wwwroot/<you_host> -n <you_host> -s
```
2. 创建 Https 和 Http 站点
```shell script
# 首先先创建一个 Http Only 站点
bin/vhost-gen -p /data/wwwroot/<you_host> -n <you_host> -s

# 然后到 Nginx-Proxy-Manager 面板中添加站点，确保站点能通过 Http 被访问到
# 接着在 Nginx-Proxy-Manager 面板中配置站点的 SSL 证书，确保站点能通过 Http 被访问到

# 如果你的应用程序不需要源站点也是 Https，那么此时就可以不用进行下一步操作了
# 如果你的应用程序需要 Https，比如 Laravel，那么你就需要为 apache 生成 Https 的配置文件
bin/vhost-gen -p /data/wwwroot/<you_host> -n <you_host> -s -m npm-<id>
# ID 请打开 NPM 面板进到 Proxy Hosts 页面，通过浏览器的开发工具，找到 /api/nginx/proxy-hosts 的请求记录，里面有站点的详细信息。

# 最后重启下 apache，使配置生效
docker restart apache
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
