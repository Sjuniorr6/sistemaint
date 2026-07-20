// Pedágio inline (DD-014/M3 subtask 3) — vanilla JS, sem libs.
// Cada .js-pedagio-input envia o novo pedágio no blur e atualiza o valor_agente
// da linha com o que o endpoint recalculou. Enter só força o blur (sem duplicar).
(function () {
  "use strict";

  // CSRF: token do hidden do {% csrf_token %}, enviado no header X-CSRFToken.
  var csrfEl = document.querySelector("input[name=csrfmiddlewaretoken]");
  var csrfToken = csrfEl ? csrfEl.value : "";

  function aoFocar(event) {
    // Guarda o valor original para comparar no blur e restaurar em caso de erro.
    event.target.dataset.original = event.target.value;
  }

  function aoTeclar(event) {
    // Enter apenas tira o foco — o envio acontece no blur, uma única vez.
    if (event.key === "Enter") {
      event.preventDefault();
      event.target.blur();
    }
  }

  function aoSair(event) {
    var input = event.target;
    var original = input.dataset.original;

    // Nada mudou → não faz nada.
    if (input.value === original) {
      return;
    }

    var linha = input.closest("tr");
    var celulaValor = linha
      ? linha.querySelector("[data-valor-agente]")
      : null;

    var corpo = "pedagio=" + encodeURIComponent(input.value);

    input.disabled = true;
    fetch(input.dataset.url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrfToken,
      },
      body: corpo,
    })
      .then(function (resposta) {
        if (!resposta.ok) {
          throw new Error("falha");
        }
        return resposta.json();
      })
      .then(function (dados) {
        // 200 → sincroniza a célula do valor_agente (com vírgula) e o input.
        if (celulaValor) {
          // valor_agente null = pendente sem franquia (DD-068) → "—", como no template.
          celulaValor.textContent =
            dados.valor_agente === null
              ? "—"
              : dados.valor_agente.replace(".", ",");
        }
        input.value = dados.pedagio;
        input.dataset.original = input.value;
      })
      .catch(function () {
        // Erro → avisa e restaura o valor que estava antes da edição.
        alert("Não foi possível atualizar o pedágio. Tente novamente.");
        input.value = original;
      })
      .finally(function () {
        input.disabled = false;
      });
  }

  var inputs = document.querySelectorAll(".js-pedagio-input");
  for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("focus", aoFocar);
    inputs[i].addEventListener("keydown", aoTeclar);
    inputs[i].addEventListener("blur", aoSair);
  }
})();
