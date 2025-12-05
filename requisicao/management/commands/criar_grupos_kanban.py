from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from requisicao.models import Requisicoes


class Command(BaseCommand):
    help = 'Cria os grupos de permissão para o Kanban'

    def handle(self, *args, **options):
        # Pegar o ContentType de Requisicoes
        content_type = ContentType.objects.get_for_model(Requisicoes)
        
        # Criar ou pegar permissões necessárias
        view_permission = Permission.objects.get(
            codename='view_requisicoes',
            content_type=content_type
        )
        change_permission = Permission.objects.get(
            codename='change_requisicoes',
            content_type=content_type
        )
        
        # Criar grupo Gestão Kanban
        gestao_group, created = Group.objects.get_or_create(name='Gestão Kanban')
        if created:
            gestao_group.permissions.add(view_permission, change_permission)
            self.stdout.write(
                self.style.SUCCESS('Grupo "Gestão Kanban" criado com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Grupo "Gestão Kanban" já existe.')
            )
        
        # Criar grupo Configuração Kanban
        config_group, created = Group.objects.get_or_create(name='Configuração Kanban')
        if created:
            config_group.permissions.add(view_permission, change_permission)
            self.stdout.write(
                self.style.SUCCESS('Grupo "Configuração Kanban" criado com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Grupo "Configuração Kanban" já existe.')
            )
        
        self.stdout.write(
            self.style.SUCCESS('\nGrupos configurados:')
        )
        self.stdout.write(
            self.style.SUCCESS('  - Gestão Kanban: pode mover todos os cards e expedir')
        )
        self.stdout.write(
            self.style.SUCCESS('  - Configuração Kanban: pode adicionar IDs e mover para Auditoria')
        )
