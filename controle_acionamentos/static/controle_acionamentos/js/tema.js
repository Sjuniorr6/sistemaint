(function () {
  const CHAVE = 'gs-cac-tema';
  const escopo = document.querySelector('.acn-escopo');
  const botao = document.getElementById('acn-btn-tema');
  const rotulo = document.getElementById('acn-rotulo-tema');
  if (!escopo || !botao || !rotulo) { return; }
  const gsCacTema = {
    aplicar: function (tema) {
      escopo.classList.toggle('acn-ambar', tema === 'ambar');
      rotulo.textContent = tema === 'ambar' ? 'Âmbar' : 'Noite';
      localStorage.setItem(CHAVE, tema);
    },
    alternar: function () {
      const atual = localStorage.getItem(CHAVE) || 'noite';
      this.aplicar(atual === 'ambar' ? 'noite' : 'ambar');
    },
    init: function () {
      this.aplicar(localStorage.getItem(CHAVE) || 'noite');
    }
  };
  botao.addEventListener('click', function () { gsCacTema.alternar(); });
  window.gsCacTema = gsCacTema;
  gsCacTema.init();
}());
