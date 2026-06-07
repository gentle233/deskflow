const t="deskflow_server_url";function o(){return localStorage.getItem(t)||""}function s(e){localStorage.setItem(t,e)}function n(e){const r=o();return r?`${r}${e}`:e}export{n as a,o as g,s};
