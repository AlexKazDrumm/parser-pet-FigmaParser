from figma_exporter.css import (
    auto_layout_css,
    node_css_block,
    paint_to_css,
    rgb_to_css,
    to_safe_class,
)


def test_rgb_to_css_hex_and_rgba():
    assert rgb_to_css({"r": 1, "g": 1, "b": 1, "a": 1}) == "#ffffff"
    assert rgb_to_css({"r": 0, "g": 0, "b": 0, "a": 0.5}) == "rgba(0,0,0,0.50)"


def test_paint_to_css_variants():
    assert (
        paint_to_css({"type": "SOLID", "color": {"r": 0.145, "g": 0.388, "b": 0.922, "a": 1}})
        == "#2563eb"
    )
    assert (
        paint_to_css({"type": "SOLID", "visible": False, "color": {"r": 1, "g": 1, "b": 1}})
        == "transparent"
    )
    grad = paint_to_css(
        {
            "type": "GRADIENT_LINEAR",
            "gradientStops": [
                {"position": 0, "color": {"r": 0, "g": 0, "b": 0, "a": 1}},
                {"position": 1, "color": {"r": 1, "g": 1, "b": 1, "a": 1}},
            ],
        }
    )
    assert grad == "linear-gradient(90deg, #000000 0%, #ffffff 100%)"


def test_to_safe_class_sanitises():
    assert to_safe_class("Login Card / Title:1") == "Login_Card____Title_1"
    assert to_safe_class("1 Frame").startswith("_1")
    assert to_safe_class("") == "_node"


def test_auto_layout_css_horizontal():
    lines = auto_layout_css(
        {
            "layoutMode": "HORIZONTAL",
            "itemSpacing": 8,
            "paddingTop": 4,
            "paddingRight": 4,
            "paddingBottom": 4,
            "paddingLeft": 4,
            "primaryAxisAlignItems": "SPACE_BETWEEN",
            "counterAxisAlignItems": "CENTER",
        }
    )
    joined = "\n".join(lines)
    assert "display: flex;" in joined
    assert "flex-direction: row;" in joined
    assert "gap: 8px;" in joined
    assert "justify-content: space-between;" in joined
    assert "align-items: center;" in joined


def test_node_css_block_text_has_color_not_background():
    block = node_css_block(
        {
            "id": "10:3",
            "type": "TEXT",
            "style": {"fontSize": 24, "fontWeight": 700},
            "fills": [{"type": "SOLID", "color": {"r": 0.09, "g": 0.09, "b": 0.11, "a": 1}}],
        },
        "Title",
        0,
        0,
        100,
        32,
    )
    assert "color: #17171c;" in block
    assert "background:" not in block
    assert "white-space: pre-wrap;" in block
