---
title: Understanding the way Solara server works
description: Solara server enables running ipywidgets-based applications as standalone dashboards and apps, allowing multiple "Virtual kernels" to share
   the same process for better performance and scalability.
---
# Solara server

The solara server enables running ipywidgets based applications without a real Jupyter kernel, allowing multiple "Virtual kernels" to share the same process for better performance and scalability.

## Installation

To install the solara server, run:

```bash
$ pip install "solara-server[starlette]"
$ # pip install solara # to get all solara packages
```

See [our installation guide](/documentation/getting_started/installing) for more information.

## WebSocket in Solara
Solara uses a WebSocket to transmit state and updates directly from the server to the browser. This ensures that the state remains centralized on the server, facilitating state transitions server-side and enabling live updates to be pushed directly to the browser.


## Virtual Kernels
Normally when a browser page connects to a Solara server, a virtual kernel is created and is assigned a unique identifier termed a "Kernel ID." Should a WebSocket disconnection occur, Solara attempts to re-establish the connection, sending the Kernel ID during this process. If the server recognizes this ID (and the requested kernel hasn't expired) the Solara app resumes operations seamlessly.

### Virtual kernel lifecycle
Closing a browser page will directly shut the virtual kernel down (if this page was the last known page to the Solara server). This ensures that active closing of pages will directly clean up any memory usage on the server side for this kernel.

However, when the websocket between the web page and the server disconnects, the server keeps the kernel alive for 24 hours after the closure of the last WebSocket connection. The duration is customizable through the `SOLARA_KERNEL_CULL_TIMEOUT` environment variable. This feature is particularly handy in scenarios where devices like computers hibernate, leading to WebSocket disconnections. Upon awakening and subsequent WebSocket reconnection, the Solara app picks up right where it left off.

To optimize memory usage or address specific needs, one might opt for a shorter expiration duration. For instance, setting `SOLARA_KERNEL_CULL_TIMEOUT=1m` will cause sessions to expire after just 1 minute. Other possible options are `2d` (2 days), `3h` (3 hours), `30s` (30 seconds), etc. If no units are given, seconds are assumed.

### Maximum number of kernels connected

Each virtual kernel runs in its own thread, this ensures that one particular user (actually browser page) cannot block the execution of another virtual kernel. However, each thread consumes a bit of resources. If you want to limit the number of kernels, this can be done by setting the `SOLARA_KERNELS_MAX_COUNT` environment variable. The default is unlimited (empty string), but you can set it to any number you like. If the limit is reached, the server will refuse new connections until a kernel is closed.


## Handling Multiple Workers

In setups with multiple workers, it's possible for a page to (re)connect to a different worker than its original. This can happen after a lost network connection is restored, or when [ipypopout](https://github.com/widgetti/ipypopout) is used, since ipypopout creates a new connection, which can end up at a different worker. This can result in a loss of the virtual kernel, since it lives on the worker that was first connected to. The Solara app will then initiate a fresh start, or simply fail when ipypopout is used. To prevent this scenario, a sticky session configuration is recommended, ensuring consistent client-worker connections. A load balancer, such as [nginx](https://www.nginx.com/), can be used to achieve this. Note that using multiple workers (e.g. by using gunicorn) cannot work since a connection will be made to a different worker each time.

If you have questions about setting this up, or require assistance, please [contact us](https://solara.dev/docs/contact).

## Sessions

Solara uses a browser cookie (named `solara-session-id`) to store a unique session id. This session id is available via [get_session_id()](https://solara.dev/api/get_session_id) and is the same for all
browser pages. This can be used to store state that outlives a page refresh.

We recommend storing the state in an external database, especially in the case of multiple workers/nodes. If you want to store state associated to a session in-memory, make sure to set up sticky sessions.


The `solara-session-id` cookie is accessible in the browser using JavaScript. If you deem this a security risk, you can disable the cookie by setting the `SOLARA_SESSION_HTTP_ONLY` environment variable to `True`.


## Readiness check

To check if the server is ready to accept request, the `/readyz` endpoint is added, and should return a 200 HTTP status code, e.g.:

```
$ curl http://localhost:8765/readyz
curl -I localhost:8765

HTTP/1.1 200 OK
...
```

## Live resource information


To check resource usage of the server (CPU, memory, etc.), the `/resourcez` endpoint is added, and should return a 200 HTTP status code and include
various resource information, like threads created and running, number of virtual kernels, etc. in JSON format. To get also memory and cpu usage, you can include
the `?verbose` query parameter, e.g.:

```
$ curl http://localhost:8765/resourcez\?verbose
```

The JSON format may be subject to change.

## Ignoring notebook extensions

Not all (classic) jupyter notebook extensions are compatible with Solara, and there is not way to distinguish between notebook extensions that are needed for widgets and those that are not.
To ignore notebook extensions, you can set the `SOLARA_SERVER_IGNORE_NBEXTENSIONS` environment variable. This is a comma separated list of notebook extensions to ignore. For example, to ignore the `dash/main` and `foo/bar` extensions, you can run:

```bash
$ SOLARA_SERVER_IGNORE_NBEXTENSIONS="dash/main,foo/bar" solara run nogit/sol.py -a
```

Note that these error are not fatal, and the Solara app will still run.

## Production mode

By default, solara runs in development mode. This means, it will:

   * Automatically [reload your project files](/documentation/advanced/reference/reloading) by watching files on the filesystemn
   * Load debug version of the CSS files and JavaScript files for improved error messages (which leads to larger asset files).

To disabled all of these option, pass the `--production` flag, or set the environment variable `SOLARA_MODE=production`.

## Telemetry

Solara uses Mixpanel to collect usage of the solara server. We track when a server is started, stopped and a daily report of the number of unique users and connections made. To opt out of mixpanel telemetry, either:

 * Set the environmental variable `SOLARA_TELEMETRY_MIXPANEL_ENABLE` to `False`.
 * Install [python-dotenv](https://pypi.org/project/python-dotenv/) and put `SOLARA_TELEMETRY_MIXPANEL_ENABLE=False` in a `.env` file.
 * Run in auto restart mode (e.g. using `$ solara run sol.py --auto-restart`)
