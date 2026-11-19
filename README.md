# DeXtop

DeXtop est une application de bureau open source qui lance des écrans Android virtuels avec scrcpy.

## Utilisation

1. Installez Python 3.10 ou une version plus récente.
2. Installez les dépendances :
   ```bash
   pip install -e .
   ```
3. Placez `scrcpy` et `adb` dans le dossier `bin/`, ou ajoutez-les au `PATH`.
4. Lancez l'application :
   ```bash
   python -m dextop
   ```

Pour une utilisation en ligne de commande :

```bash
dextop --list
dextop --width 1920 --height 1080 --dpi 240
```
