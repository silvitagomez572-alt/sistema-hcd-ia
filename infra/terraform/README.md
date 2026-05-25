# infra/terraform/

Infraestructura como código — placeholder.

Este directorio sigue el patrón del proyecto de referencia `hospital-triage-ia`.
La infraestructura de despliegue del sistema HCD IA no está implementada en esta versión.

## Configuración prevista

En caso de despliegue en producción, este directorio contendría:

- `provider.tf` — proveedor de nube (GCP / AWS / Azure)
- `main.tf` — recursos principales (Cloud Run, GKE, o VM)
- `variables.tf` — parámetros configurables
- `outputs.tf` — salidas (URLs, IPs)
- `backend.tf` — estado remoto de Terraform
- `terraform.tfvars.example` — ejemplo de variables sin valores sensibles

## Estado

Pendiente de implementación. Sistema ejecutándose en localhost para esta versión.
