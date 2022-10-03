terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

/* APPLY

-- deploy infra -- 
terraform apply -var="digitalocean_token=${DIGITALOCEAN_TOKEN}"
  
-- start app on droplet --
cd /astro/
apt-get install -y docker.io docker-compose &&\
docker build ./frontend -t dmw2151/astro_frontend &&\
docker build . -t dmw2151/tle_tb_astro

docker-compose up --scale tlesub=5
*/

provider "digitalocean" {
  token = var.digitalocean_token
}

variable "digitalocean_token" {
  type      = string
  sensitive = true
}

// requires pre-existing SSH key named `droplet` exists and is available
// data: https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/data-sources/ssh_key
data "digitalocean_ssh_key" "droplet" {
  name = "droplet"
}

// https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/data-sources/domain
data "digitalocean_domain" "target" {
  name = "dmw2151.com"
}

// generate wildcard cert for the domain
// resources: https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/resources/certificate
resource "digitalocean_certificate" "cert" {
  name    = "do-astro-${data.digitalocean_domain.target.name}-lets-encrypt-cert"
  type    = "lets_encrypt"
  domains = [data.digitalocean_domain.target.name, "astro.${data.digitalocean_domain.target.name}"]
}

// record for the edge api - public use
// resource: https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/resources/record
resource "digitalocean_record" "astro" {
  domain = data.digitalocean_domain.target.id
  type   = "A"
  name   = "astro"
  value  = digitalocean_droplet.main.ip
  ttl    = 300
}

// single instance w. everything running...
// resource: https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/resources/droplet
resource "digitalocean_droplet" "main" {

  // basic
  name     = "astro-main"
  image    = "ubuntu-22-04-x64"
  size     = "s-2vcpu-4gb-amd"
  region   = "nyc3"
  ssh_keys = [data.digitalocean_ssh_key.droplet.id]
}
