"""Security and build verification tests for the static blog generator."""

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build  # noqa: E402
import rich_text  # noqa: E402


def _make_approved_post(
    *,
    post_id="0123456789ab",
    title="Titulo de teste seguro",
    body="Conteudo editorial suficientemente longo para passar na validacao.",
    category="Tecnologia",
    cover="paisagem",
    cover_sha256,
    cover_alt="Descricao da capa",
    cover_credit="",
    document=None,
    project=None,
    version=1,
    published_at="2026-11-21T12:00:00+00:00",
    extra=None,
):
    approved = {
        "title": title,
        "body": body,
        "category": category,
        "cover": cover,
        "cover_sha256": cover_sha256,
        "cover_alt": cover_alt,
        "cover_credit": cover_credit,
    }
    if document is not None:
        approved["document"] = document
    if project is not None:
        approved["project"] = project
    digest = hashlib.sha256(
        json.dumps(approved, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    post = dict(approved)
    post.update(
        {
            "id": post_id,
            "version": version,
            "digest": digest,
            "approval_digest": hashlib.sha256(b"approval").hexdigest(),
            "published_at": published_at,
            "updated_at": published_at,
        }
    )
    if extra:
        post.update(extra)
    return post


def _create_temp_site(tmp_dir: Path, posts=None):
    assets = tmp_dir / "assets"
    (assets / "covers").mkdir(parents=True)
    content = tmp_dir / "content"
    content.mkdir(parents=True)
    for asset_name in ("paisagem.webp", "style.css", "site.js", "favicon.svg"):
        shutil.copy2(ROOT / "assets" / asset_name, assets / asset_name)
    cover_sha = hashlib.sha256((assets / "paisagem.webp").read_bytes()).hexdigest()
    if posts is None:
        posts = [_make_approved_post(cover_sha256=cover_sha)]
    manifest = {"schema_version": 1, "posts": posts}
    (content / "posts.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cover_sha


class _HtmlTagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class HtmlEscapingTests(unittest.TestCase):
    XSS_PAYLOAD = '<script>alert(1)</script>'
    ATTR_PAYLOAD = '"><img src=x onerror=alert(1)>'

    def _assert_no_injected_elements(self, html_text, expected_script_suffix="assets/site.js"):
        parser = _HtmlTagCollector()
        parser.feed(html_text)
        for tag, attrs in parser.tags:
            self.assertNotIn("onerror", attrs, f"Atributo onerror inesperado em <{tag}>")
            if tag == "script":
                self.assertTrue(
                    attrs.get("src", "").endswith(expected_script_suffix),
                    f"Tag <script> inesperada: {attrs}",
                )
            if tag == "img":
                self.assertNotEqual(attrs.get("src"), "x", f"Tag <img> injetada: {attrs}")
        return parser.tags

    def test_page_escapes_title_and_description(self):
        html = build.page(
            f"Titulo {self.XSS_PAYLOAD}",
            "<p>Corpo</p>",
            description=f"Desc {self.ATTR_PAYLOAD}",
        )
        self._assert_no_injected_elements(html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&quot;&gt;&lt;img src=x onerror=alert(1)&gt;", html)

    def test_post_card_escapes_attributes_and_metadata(self):
        post = {
            "id": "abcdef012345",
            "title": f"Post {self.XSS_PAYLOAD}",
            "body": f"Texto {self.ATTR_PAYLOAD} suficientemente longo",
            "category": f'Tecnologia {self.ATTR_PAYLOAD}',
            "cover": "paisagem",
            "project": {
                "id": "fedcba987654",
                "name": f"Proj {self.ATTR_PAYLOAD}",
                "description": f"Desc {self.XSS_PAYLOAD}",
            },
        }
        card = build.post_card(post)
        tags = self._assert_no_injected_elements(card)
        article_attrs = dict(tags)[ "article" ] if False else next(a for t, a in tags if t == "article")
        self.assertEqual(article_attrs["data-category"], post["category"])
        self.assertIn(self.XSS_PAYLOAD, article_attrs["data-search"])
        self.assertIn(self.ATTR_PAYLOAD, article_attrs["data-search"])
        self.assertIn("&quot;&gt;&lt;img src=x onerror=alert(1)&gt;", card)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", card)

    def test_article_body_escapes_metadata_and_plain_body(self):
        post = {
            "id": "abcdef012345",
            "title": f"Titulo {self.XSS_PAYLOAD}",
            "body": f"Paragrafo {self.XSS_PAYLOAD} {self.ATTR_PAYLOAD}",
            "category": f"Tecnologia {self.ATTR_PAYLOAD}",
            "cover": "paisagem",
            "cover_alt": f"Alt {self.ATTR_PAYLOAD}",
            "cover_credit": f"Credito {self.XSS_PAYLOAD}",
            "project": {
                "id": "fedcba987654",
                "name": f"Proj {self.XSS_PAYLOAD}",
                "description": "Descricao valida",
            },
        }
        rendered = build.article_body(post, f"../assets/{self.ATTR_PAYLOAD}", "21/11/2026")
        tags = self._assert_no_injected_elements(rendered)
        cover_img = next(a for t, a in tags if t == "img" and "article-cover" in a.get("class", ""))
        self.assertEqual(cover_img["alt"], post["cover_alt"])
        self.assertNotIn("<script>alert(1)</script>", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertIn("&quot;&gt;&lt;img src=x onerror=alert(1)&gt;", rendered)

    def test_build_escapes_xss_in_all_editorial_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cover_sha = _create_temp_site(root, posts=[])
            post = _make_approved_post(
                title=f"Titulo {self.XSS_PAYLOAD} {self.ATTR_PAYLOAD}",
                body=f"Corpo seguro {self.XSS_PAYLOAD} {self.ATTR_PAYLOAD} longo.",
                cover_sha256=cover_sha,
                cover_alt=f"Alt {self.ATTR_PAYLOAD}",
                cover_credit=f"Cred {self.XSS_PAYLOAD}",
                project={
                    "id": "fedcba987654",
                    "name": f"Nome {self.ATTR_PAYLOAD}",
                    "description": f"Desc {self.XSS_PAYLOAD}",
                },
            )
            (root / "content" / "posts.json").write_text(
                json.dumps({"schema_version": 1, "posts": [post]}, ensure_ascii=False),
                encoding="utf-8",
            )
            out = build.build(root)
            for html_file in out.rglob("*.html"):
                text = html_file.read_text(encoding="utf-8")
                self._assert_no_injected_elements(text)
                self.assertNotIn("<script>alert(1)</script>", text, str(html_file))


class RichTextSecurityTests(unittest.TestCase):
    def test_allowlisted_nodes_and_marks_escape_html(self):
        doc = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "<script>alert(1)</script>"}],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "<b>Bold</b>",
                            "marks": [{"type": "bold"}],
                        },
                        {"type": "hardBreak"},
                        {
                            "type": "text",
                            "text": 'Link "seguro"',
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {
                                        "href": 'https://example.com/?a=1&b="2"'
                                    },
                                }
                            ],
                        },
                    ],
                },
            ],
        }
        html = rich_text.render_document(doc)
        self.assertIn("<h2>&lt;script&gt;alert(1)&lt;/script&gt;</h2>", html)
        self.assertIn("<strong>&lt;b&gt;Bold&lt;/b&gt;</strong>", html)
        self.assertIn(
            '<a href="https://example.com/?a=1&amp;b=&quot;2&quot;" rel="noopener noreferrer">Link &quot;seguro&quot;</a>',
            html,
        )

    def test_valid_schemes_accepted(self):
        for href in (
            "https://example.com/artigo",
            "http://example.com/caminho",
            "mailto:contato@example.com",
        ):
            doc = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "link",
                                "marks": [{"type": "link", "attrs": {"href": href}}],
                            }
                        ],
                    }
                ],
            }
            rendered = rich_text.render_document(doc)
            self.assertIn('rel="noopener noreferrer"', rendered)

    def test_dangerous_and_malformed_urls_rejected(self):
        bad_urls = [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            " javascript:alert(1)",
            "https://example.com ",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
            "https://user:pass@example.com/",
            "https://user@example.com/",
            "https://example.com/\nX-Evil: 1",
            "mailto://evil.com",
            "mailto:",
            "",
        ]
        for href in bad_urls:
            doc = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "click",
                                "marks": [{"type": "link", "attrs": {"href": href}}],
                            }
                        ],
                    }
                ],
            }
            with self.subTest(href=href):
                with self.assertRaises(ValueError):
                    rich_text.validate_document(doc)

    def test_disallowed_nodes_marks_attrs_depth_and_size_rejected(self):
        disallowed_docs = [
            {"type": "doc", "content": [{"type": "html", "text": "<script>1</script>"}]},
            {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": "H1"}],
                    }
                ],
            },
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "attrs": {"onclick": "alert(1)"},
                        "content": [{"type": "text", "text": "oi"}],
                    }
                ],
            },
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "oi",
                                "marks": [{"type": "textStyle", "attrs": {"color": "red"}}],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "oi",
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {"href": "https://example.com", "onclick": "x"},
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
        for doc in disallowed_docs:
            with self.assertRaises(ValueError):
                rich_text.validate_document(doc)

        # Excessive nesting depth (> 16)
        nested = {"type": "paragraph", "content": [{"type": "text", "text": "fundo"}]}
        for _ in range(18):
            nested = {"type": "blockquote", "content": [nested]}
        with self.assertRaises(ValueError):
            rich_text.validate_document({"type": "doc", "content": [nested]})

        # Oversized document (> 240000 JSON chars)
        huge = {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "a" * 250000}]}],
        }
        with self.assertRaises(ValueError):
            rich_text.validate_document(huge)


class ManifestAndPathContainmentTests(unittest.TestCase):
    def _build_with_mutated_manifest(self, mutator):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_temp_site(root)
            manifest_path = root / "content" / "posts.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mutator(manifest, root)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build.build(root)

    def test_invalid_schema_version_rejected(self):
        self._build_with_mutated_manifest(lambda m, _: m.__setitem__("schema_version", 2))

    def test_path_traversal_and_duplicate_id_rejected(self):
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("id", "../../etc/passwd")
        )
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"].append(dict(m["posts"][0]))
        )

    def test_invalid_category_and_cover_traversal_rejected(self):
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("category", "Outra")
        )
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("cover", "../README.md")
        )
        with self.assertRaises(ValueError):
            build.cover_path({"cover": "../README.md"})

    def test_tampered_cover_sha_and_digest_and_cover_source_rejected(self):
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("cover_sha256", "0" * 64)
        )
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("digest", "0" * 64)
        )
        self._build_with_mutated_manifest(
            lambda m, _: m["posts"][0].__setitem__("cover_source", "/private/secret.png")
        )

    def test_invalid_published_at_and_version_rejected(self):
        for bad_date in ("not-a-date", 12345, None):
            self._build_with_mutated_manifest(
                lambda m, _, d=bad_date: m["posts"][0].__setitem__("published_at", d)
            )
        for bad_version in (0, -1, True, "1", None):
            self._build_with_mutated_manifest(
                lambda m, _, v=bad_version: m["posts"][0].__setitem__("version", v)
            )

    def test_safe_output_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            out.mkdir()
            with self.assertRaises(ValueError):
                build._safe_output_path(out, "..", "fora.html")
            with self.assertRaises(ValueError):
                build._safe_output_path(out, "textos", "..", "..", "fora.html")
            with self.assertRaises(ValueError):
                build._safe_output_path(out)

    def test_rejects_symlink_dist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_temp_site(root)
            target = root / "outside_dir"
            target.mkdir()
            dist = root / "dist"
            try:
                dist.symlink_to(target, target_is_directory=True)
            except OSError:
                orig_is_symlink = Path.is_symlink
                with patch.object(
                    Path,
                    "is_symlink",
                    lambda p: True if p == dist else orig_is_symlink(p),
                ):
                    with self.assertRaises(ValueError):
                        build.build(root)
            else:
                with self.assertRaises(ValueError):
                    build.build(root)

    def test_rejects_symlink_inside_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_temp_site(root)
            secret = root / "secret.txt"
            secret.write_text("nao-exportar", encoding="utf-8")
            evil = root / "assets" / "leak.txt"
            try:
                evil.symlink_to(secret)
            except OSError:
                evil.write_text("placeholder", encoding="utf-8")
                orig_is_symlink = Path.is_symlink
                with patch.object(
                    Path,
                    "is_symlink",
                    lambda p: True if p == evil else orig_is_symlink(p),
                ):
                    with self.assertRaises(ValueError):
                        build.build(root)
            else:
                with self.assertRaises(ValueError):
                    build.build(root)


class BuildArtifactAndWorkflowTests(unittest.TestCase):
    SECRET_PATTERNS = [
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{10,}"),
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{10,}"),
        re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{16,}"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"\bcover_source\b"),
    ]

    def test_end_to_end_build_artifact_is_clean_and_hardened(self):
        out = build.build(ROOT)
        self.assertTrue(out.is_dir())

        rel_files = {
            p.relative_to(out).as_posix()
            for p in out.rglob("*")
            if p.is_file()
        }
        expected_top = {
            "index.html",
            "sobre.html",
            "projetos.html",
            "404.html",
            "publications.json",
            ".nojekyll",
        }
        self.assertTrue(expected_top.issubset(rel_files))

        allowed_patterns = (
            r"^(index|sobre|projetos|404)\.html$",
            r"^publications\.json$",
            r"^\.nojekyll$",
            r"^assets/(favicon\.svg|paisagem\.webp|site\.js|style\.css)$",
            r"^assets/covers/[a-f0-9]{64}\.webp$",
            r"^textos/[a-f0-9]{12}\.html$",
            r"^projetos/[a-f0-9]{12}\.html$",
        )
        for rel in rel_files:
            self.assertTrue(
                any(re.fullmatch(pat, rel) for pat in allowed_patterns),
                f"Arquivo inesperado em dist/: {rel}",
            )

        manifest = json.loads((ROOT / "content" / "posts.json").read_text(encoding="utf-8"))
        for post in manifest["posts"]:
            self.assertIn(f"textos/{post['id']}.html", rel_files)

        pubs = json.loads((out / "publications.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pubs), {"schema_version", "commit", "posts"})
        for entry in pubs["posts"]:
            self.assertEqual(set(entry), {"id", "version", "approval_digest"})

        for rel in rel_files:
            if not rel.endswith((".html", ".json", ".js", ".css", ".svg")):
                continue
            text = (out / rel).read_text(encoding="utf-8")
            for pat in self.SECRET_PATTERNS:
                self.assertIsNone(pat.search(text), f"Padrao suspeito em {rel}")
            if rel.endswith(".html"):
                self.assertIn(
                    f'<meta http-equiv="Content-Security-Policy" content="{build.CSP_POLICY}">',
                    text,
                    rel,
                )
                self.assertIn(
                    '<meta name="referrer" content="strict-origin-when-cross-origin">',
                    text,
                    rel,
                )
                for m in re.finditer(r'<a\b[^>]*target="_blank"[^>]*>', text):
                    tag = m.group(0)
                    self.assertIn("noopener", tag, f"Link sem noopener em {rel}")
                    self.assertIn("noreferrer", tag, f"Link sem noreferrer em {rel}")

    def test_github_actions_workflow_is_sha_pinned_and_least_privilege(self):
        workflow_path = ROOT / ".github" / "workflows" / "pages.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        uses_refs = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
        self.assertGreaterEqual(len(uses_refs), 5)
        for ref in uses_refs:
            self.assertRegex(
                ref,
                r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$",
                f"Action nao fixada por SHA completo: {ref}",
            )

        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("write-all", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)

        dependabot_path = ROOT / ".github" / "dependabot.yml"
        self.assertTrue(dependabot_path.is_file())
        dependabot = dependabot_path.read_text(encoding="utf-8")
        self.assertIn('package-ecosystem: "github-actions"', dependabot)


if __name__ == "__main__":
    unittest.main()
