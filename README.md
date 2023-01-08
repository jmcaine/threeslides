# threeslides
Distributed / multi-host slide presentation system

## Install and Configuration

	$ python3 -m venv ve
	$ . ve/bin/activate
	$ pip install --upgrade pip
	$ git clone git@github.com:jmcaine/threeslides.git
	$ pip install -r threeslides/requirements.txt

(Note, the pip install may rely on apt-installs like build-essential, libffi-dev, python3-dev, ...)

Create the database ('apt install sqlite3' will be required for this, of course)::

	$ cat main.sql | sqlite3 main.db

And run your app::

	$ cd threeslides
	$ python -m aiohttp.web -H localhost -P 8080 app.main:init
	
(Or, with [aiohttp-devtools](https://github.com/aio-libs/aiohttp-devtools)

	$ cd threeslides
	$ adev runserver -s static --livereload app

The adev server will run on port 8000 by default.  Other adev options may be
desirable, and additions like [aiohttp-debugtoolbar](https://github.com/aio-libs/aiohttp-debugtoolbar)
might be useful.

