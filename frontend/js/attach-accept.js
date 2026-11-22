// attach-accept.js: the one list of files a note or a chat message takes, a file of its own so the
// boot scripts do not carry it: the chat input reads it when the Chat tab is built (wiring.js) and the
// capture card's staging reads it when the card opens (capture-card.js), in the app and on the desk.

//: **The one list of files a note or chat message takes**: chat's picker and the Quick
//: capture card's both read it (wiring.js sets the chat input's `accept`). `docview.VIEWABLE_SUFFIXES`
//: plus any image; `ATTACHMENT_SUFFIXES` takes all of it (tests/test_docview.py).
(() => {
  const ATTACH_ACCEPT = "image/*,.pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.odt,.rtf,.epub,.txt,.text,.log,.csv,.tsv,.md,.markdown,.html,.htm,.json,.xml,.yaml,.yml,.py,.js,.mjs,.cjs,.ts,.tsx,.jsx,.css,.scss,.sass,.styl,.less,.java,.c,.h,.cpp,.hpp,.cs,.go,.rs,.rb,.php,.swift,.kt,.r,.sh,.bash,.zsh,.sql,.toml,.ini,.cfg,.diff,.patch,.vb,.vbs,.dockerfile,.mk";
  Object.assign(window, { ATTACH_ACCEPT });
})();
