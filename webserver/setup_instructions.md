# Setup new ubuntu webserver


## Pre-Setup
Remove the firewall from the machine (Network tab in Linode machine view)
```bash
sudo apt update
sudo apt install python3 python3-venv libaugeas0 -y
apt upgrade -y
reboot
```
Wait for machine to boot

## NGINX
```bash
sudo apt install nginx -y
```

## CERTBOT - ssl cert
remove the firewall from the machine
```bash
sudo python3 -m venv /opt/certbot/
sudo /opt/certbot/bin/pip install --upgrade pip
sudo /opt/certbot/bin/pip install certbot certbot-nginx
sudo ln -s /opt/certbot/bin/certbot /usr/bin/certbot
sudo certbot --nginx
```

## CERTBOT - auto renewal (Optional)
```bash
SLEEPTIME=$(awk 'BEGIN{srand(); print int(rand()*(3600+1))}'); echo "0 0,12 * * * root sleep $SLEEPTIME && certbot renew -q" | sudo tee -a /etc/crontab > /dev/null
sudo sh -c 'printf "#!/bin/sh\nservice haproxy stop\n" > /etc/letsencrypt/renewal-hooks/pre/haproxy.sh'
sudo sh -c 'printf "#!/bin/sh\nservice haproxy start\n" > /etc/letsencrypt/renewal-hooks/post/haproxy.sh'
sudo chmod 755 /etc/letsencrypt/renewal-hooks/pre/haproxy.sh
sudo chmod 755 /etc/letsencrypt/renewal-hooks/post/haproxy.sh
```

## Setup custom webserver 

### Create pyserver.py
```bash
nano pyserver.py
```
Copy code from: auto_etp/linodeWebserver/server.py
```bash
chmod 777 pyserver.py
```

### Create python_server.service
```bash
sudo nano /etc/systemd/system/python_server.service
```
```
[Unit]
Description=Python TCP and UDP Server
After=network.target

[Service]
User=root
WorkingDirectory=/root/python_server
ExecStart=/usr/bin/python3 pyserver.py
Restart=always
RestartSec=5
WorkingDirectory=/root

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable python_server
sudo systemctl start python_server
sudo systemctl status python_server
```


## IPERF3
```bash
sudo apt -y install iperf3
```
select ```<yes>```


## Add clock to nginix
```bash
nano /var/www/html/index.nginx-debian.html
```
Copy code from auto_etp/linodeWebserver/index.nginx-debian.html
```bash
nginx -t
systemctl restart nginx
```

## Post-Setup
Add the firewall to the machine (Network tab in Linode machine view)
