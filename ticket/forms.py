from django import forms
from kanban_inteligencia.models import TarefaInteligencia


class TicketKanbanForm(forms.ModelForm):
    class Meta:
        model = TarefaInteligencia

        fields = [
            'titulo',
            'descricao',
            'imagem',
            # 'data_limite',
            'destinado',
            # 'responsavel',
            # 'responsavel_cor',
            'cor',
            # 'prioridade',
        ]

        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Mapeamento de Risco - Cliente X'
            }),

            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detalhes da tarefa...'
            }),

            'imagem': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),

            # 'data_limite': forms.DateInput(attrs={
            #     'class': 'form-control',
            #     'type': 'date'
            # }),

            'destinado': forms.Select(attrs={'class': 'form-control'}),

            # 'responsavel': forms.TextInput(attrs={
            #     'class': 'form-control',
            #     'placeholder': 'Nome do responsável'
            # }),

            # 'responsavel_cor': forms.Select(attrs={'class': 'form-control'}),

            'cor': forms.Select(attrs={'class': 'form-select'}),

            # 'prioridade': forms.Select(attrs={'class': 'form-select'}),
        }
