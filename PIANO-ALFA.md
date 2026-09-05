# Piano esecutivo breve

Specifica: ALPHA.md. Obiettivo: prima alfa locale realmente utilizzabile, senza esportazione NINA.

1. Dimostrare protocollo SkyChart e convenzioni coordinate. Nessuna astrometria legata al cursore manuale.
2. Implementare planner, adattatore SkyChart e HTTP locale. Test protetti: tests/test_acceptance.py; test aggiuntivi di integrazione separati. Dipendenze runtime minime.
3. Realizzare la pagina italiana dal contratto HTTP verificato. Connessione obbligatoria, modulo, tre esiti, prima finestra e timeline.
4. Revisione indipendente di codice e criteri; prove reali API/SkyChart e browser, correzioni mirate.
5. Avviare alfa e consegnare URL locale, comando di riavvio, evidenze e limiti.

Dopo l'accettazione locale: commit, merge su main e push con tag v0.2.0-alpha.1 autorizzati. Archivio storico invariato. Non modificare i criteri per ottenere test verdi.
