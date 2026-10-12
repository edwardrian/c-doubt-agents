terraform {
  required_version = "~>1.14"
  required_providers {
    vercel = {
      source  = "vercel/vercel",
      version = "~>3.0",
    }
  }
}

variable "project" {
  type        = string
  description = "nombre del proyecto"
  default     = "c-doubt-agents"
}

variable "enviroment" {
  type        = string
  description = "tipo de entorno"
  default     = "dev"


  validation {
    condition     = contains(["dev", "prod"], var.enviroment)
    error_message = "the enviroment allows is dev - prod"
  }
}


locals {
  prefix = "${var.enviroment}--${var.project}"
}
