# Despliegue del bot de Telegram en Vercel (modo webhook).
# Requiere la variable de entorno VERCEL_API_TOKEN (https://vercel.com/account/tokens).

provider "vercel" {}

locals {
  # Lee las variables del .env (CLAVE=valor) para no duplicar los secretos en Terraform
  env_lineas = [for l in split("\n", file("${path.module}/.env")) : trimspace(l) if can(regex("^[A-Za-z_][A-Za-z0-9_]*=", trimspace(l)))]
  env_archivo = {
    for l in local.env_lineas :
    split("=", l)[0] => trim(join("=", slice(split("=", l), 1, length(split("=", l)))), "\"'")
  }

  env_vercel = merge(local.env_archivo, {
    # Secreto que Telegram manda en cada petición para que solo él pueda llamar al webhook
    TELEGRAM_WEBHOOK_SECRET = sha256(local.env_archivo["TELEGRAM_BOT_TOKEN"])
  })

  dominio = "${local.prefix}.vercel.app"
}

resource "vercel_project" "bot" {
  name = local.prefix
}

resource "vercel_project_domain" "bot" {
  project_id = vercel_project.bot.id
  domain     = local.dominio
}

resource "vercel_project_environment_variable" "bot" {
  for_each = nonsensitive(toset(keys(local.env_vercel)))

  project_id = vercel_project.bot.id
  key        = each.key
  value      = local.env_vercel[each.key]
  target     = ["production"]
  sensitive  = true
}

# Sube los archivos del proyecto (respeta .vercelignore)
data "vercel_project_directory" "bot" {
  path = path.module
}

resource "vercel_deployment" "bot" {
  project_id  = vercel_project.bot.id
  files       = data.vercel_project_directory.bot.files
  path_prefix = data.vercel_project_directory.bot.path
  production  = true

  # Las variables tienen que existir antes del deploy para que el bot las lea
  depends_on = [vercel_project_environment_variable.bot]
}

# Le dice a Telegram que mande los mensajes a Vercel (se vuelve a ejecutar en cada deploy)
resource "terraform_data" "telegram_webhook" {
  triggers_replace = [vercel_deployment.bot.id, local.dominio]

  provisioner "local-exec" {
    command = "curl -fsS \"https://api.telegram.org/bot$TOKEN/setWebhook\" -d \"url=https://${local.dominio}/api/webhook\" -d \"secret_token=$SECRET\""
    environment = {
      TOKEN  = local.env_archivo["TELEGRAM_BOT_TOKEN"]
      SECRET = local.env_vercel["TELEGRAM_WEBHOOK_SECRET"]
    }
  }

  depends_on = [vercel_project_domain.bot]
}

output "webhook_url" {
  value = "https://${local.dominio}/api/webhook"
}

output "health_url" {
  value = "https://${local.dominio}/api/health"
}
