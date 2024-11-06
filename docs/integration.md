# Integration

Advice Animal is easy to adapt to your custom [advice repo](./advice_repo.md)
and any additional dependencies it needs, for installation with tools such as
`pipx`.

Sample `setup.py`:

```py
setup(
    name="advice-animal-wrapper",
    entry_points = {
        "console_scripts": [
            "advice-animal-wrapper = advice_animal_wrapper.__main__:main",
        ],
    },
    install_requires = [
        "advice-animal<1.0",
        "tomlkit",
    ],
)
```

and `__main__.py`:

```py
import advice_animal.cli
advice_animal.cli.DEFAULT_ADVICE_URL = "https://.../advice-repo"
advice_animal.cli.VERSION_PRJECT = "advice-animal-wrapper"

main = advice_animal.cli.main

if __name__ == "__main__":
    main()
```
