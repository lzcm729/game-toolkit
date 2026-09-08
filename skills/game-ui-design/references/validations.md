# Game Ui Design - Validations

## Hardcoded Screen Position

### **Id**
hardcoded-screen-position
### **Severity**
error
### **Type**
regex
### **Pattern**
position:\s*(absolute|fixed)[^}]*(left|right|top|bottom):\s*0(px)?[^}]*(left|right|top|bottom):\s*0(px)?
### **Message**
UI element positioned at exact screen corner. May be cut off on TVs due to overscan.
### **Fix Action**
Implement safe zone margins (5-10%) and allow user adjustment in settings
### **Applies To**
  - *.css
  - *.scss
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - position: absolute; left: 0; top: 0;
    - position: fixed; right: 0px; bottom: 0px;
  #### **Should Not Match**
    - position: absolute; left: 5%; top: 5%;
    - position: relative; left: 0;

## Font Size Too Small

### **Id**
small-font-size
### **Severity**
error
### **Type**
regex
### **Pattern**
font-?[Ss]ize\s*[:=]\s*["']?(?:(1[0-3]|[0-9])(?:px)?(?!\s*(?:r?em|%|v[hw]|pt))|([0-9])pt)["']?(?![0-9.])
### **Message**
Font size under 14px (or under 10pt). Too small for game UI, especially on TVs and handhelds.
相对单位（rem / em / % / vh / vw）不在此规则范围内——它们的实际像素值取决于根字号，需人工换算后判断。
### **Fix Action**
Use minimum 14px for secondary text, 16-18px for body, 24px+ for important info
### **Applies To**
  - *.css
  - *.scss
  - *.tsx
  - *.jsx
  - *.cs
  - *.gd
### **Test Cases**
  #### **Should Match**
    - font-size: 12px
    - fontSize: 10
    - fontSize="11px"
    - font-size: 8pt
  #### **Should Not Match**
    - font-size: 16px
    - fontSize: 24
    - font-size: 14px
    - font-size: 1rem
    - font-size: 1.5rem
    - font-size: 12pt

## Hardcoded Button Prompt

### **Id**
hardcoded-button-prompt
### **Severity**
error
### **Type**
regex
### **Pattern**
["'](Press|Hit|Tap|Push)\s+(A|B|X|Y|Start|Select|Space|Enter|LB|RB|LT|RT|L1|R1|L2|R2)\b[^"']*["']
### **Message**
Hardcoded button prompt. Won't adapt to controller type or key rebinding.
### **Fix Action**
Use input action names and dynamically resolve to current binding/controller glyphs
### **Applies To**
  - *.cs
  - *.gd
  - *.tsx
  - *.jsx
  - *.json
### **Test Cases**
  #### **Should Match**
    - "Press A to continue"
    - 'Hit Space to jump'
    - "Tap X"
  #### **Should Not Match**
    - GetActionPrompt("jump")
    - Press {jumpButton} to continue

## Touch Target Too Small

### **Id**
small-touch-target
### **Severity**
error
### **Type**
regex
### **Pattern**
(width|height|size)[:\s=]+["']?([0-3][0-9]|[0-9])(px|dp|pt)?["']?(?!\d)
### **Message**
Element smaller than 44px. Too small for reliable touch or controller selection.
### **Fix Action**
Minimum touch target: 44x44pt (Apple), 48x48dp (Google). Expand hit area if visual must be smaller.
### **Applies To**
  - *.css
  - *.scss
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - width: 24px
    - height: 32px
    - size: 16
  #### **Should Not Match**
    - width: 48px
    - height: 100px
    - size: 300

## Color-Only Information

### **Id**
color-only-meaning
### **Severity**
warning
### **Type**
regex
### **Pattern**
(?:(?:enemy|hostile|danger|warning|error)[^\n]*color:\s*(?:red|green|#[fF][0-9a-fA-F]{4})|color:\s*(?:red|green)[^\n]*(?:enemy|hostile|danger|warning|error))(?![^\n]*(?:icon|shape|text|label))
### **Message**
Color appears to be sole indicator. Colorblind players may not distinguish.
### **Fix Action**
Add shape, icon, or text backup for all color-coded information
### **Applies To**
  - *.css
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - enemy: { color: red }
    - color: red; // danger indicator
  #### **Should Not Match**
    - enemy: { color: red, icon: skull }

## HUD Text Without Shadow/Outline

### **Id**
no-text-shadow-outline
### **Severity**
warning
### **Type**
heuristic
### **Pattern**
class.*["'].*hud.*["'][^}]*(?!text-shadow|outline|stroke)
### **Message**
HUD text element without shadow or outline. May be unreadable on varied backgrounds.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：已有 text-shadow / outline 时仍会命中。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Add 2px contrasting outline or drop shadow to all HUD text
### **Applies To**
  - *.css
  - *.scss

## Missing Controller Navigation Setup

### **Id**
missing-controller-navigation
### **Severity**
warning
### **Type**
regex
### **Pattern**
<(button|Button|a)\b(?![^>]*(?:navigation|selectable|focusable))[^>]*>
### **Message**
Interactive element may not support controller navigation.
### **Fix Action**
Ensure element is focusable and has explicit navigation to adjacent elements
### **Applies To**
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - <button onClick={click}>Submit</button>
  #### **Should Not Match**
    - <Button navigation={nav} onClick={click}>Submit</Button>

## Long Animation Duration

### **Id**
long-animation-duration
### **Severity**
warning
### **Type**
regex
### **Pattern**
animation-?[Dd]uration[:\s=]+["']?([5-9][0-9]{2}|[1-9][0-9]{3,})(ms)?["']?|animation-?[Dd]uration[:\s=]+["']?([1-9])(s)["']?
### **Message**
Animation longer than 500ms. May cause motion discomfort for sensitive players.
### **Fix Action**
Keep UI animations under 300ms. Provide reduced motion option in settings.
### **Applies To**
  - *.css
  - *.scss
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - animation-duration: 1s
    - animationDuration: 800ms
    - animation-duration: 1500
  #### **Should Not Match**
    - animation-duration: 200ms
    - animationDuration: 300

## Fixed Pixel Dimensions

### **Id**
fixed-pixel-dimensions
### **Severity**
warning
### **Type**
regex
### **Pattern**
(width|height):\s*[0-9]{3,4}px(?!\s*\/\*.*scale|.*responsive)
### **Message**
Large fixed pixel dimensions. May not scale properly across resolutions.
### **Fix Action**
Use percentage, viewport units, or scale relative to reference resolution
### **Applies To**
  - *.css
  - *.scss
### **Test Cases**
  #### **Should Match**
    - width: 1920px
    - height: 1080px
  #### **Should Not Match**
    - width: 100%
    - height: 50vh

## Excessive Z-Index

### **Id**
z-index-war
### **Severity**
warning
### **Type**
regex
### **Pattern**
z-?[Ii]ndex[:\s=]+["']?[0-9]{4,}["']?
### **Message**
Z-index over 1000. Indicates layering system problems.
### **Fix Action**
Establish z-index scale: dropdowns 100, modals 200, tooltips 300, notifications 400
### **Applies To**
  - *.css
  - *.scss
  - *.tsx
  - *.jsx
### **Test Cases**
  #### **Should Match**
    - z-index: 9999
    - zIndex: 10000
  #### **Should Not Match**
    - z-index: 100
    - zIndex: 500

## Magic Number Positioning

### **Id**
magic-number-positions
### **Severity**
info
### **Type**
regex
### **Pattern**
(margin|padding|top|left|right|bottom)(-(top|left|right|bottom))?:\s*(?!(?:0|4|8|12|16|20|24|32|40|48|56|64|72|80|96|128)px\b)[0-9]{2,}px(?!\s*\/\*)
### **Message**
Hardcoded pixel positions. Consider using spacing scale or design tokens.
### **Fix Action**
Use spacing scale (8px, 16px, 24px, 32px) or CSS variables for consistency
### **Applies To**
  - *.css
  - *.scss
### **Test Cases**
  #### **Should Match**
    - margin: 17px
    - padding-left: 23px
  #### **Should Not Match**
    - margin: var(--space-md)
    - padding: 16px

## Missing Hover State

### **Id**
missing-hover-state
### **Severity**
warning
### **Type**
heuristic
### **Pattern**
<[Bb]utton[^>]*className=["'][^"']*["'][^>]*>(?![^<]*:hover)
### **Message**
Button without hover state indication. May confuse players about interactivity.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：hover 样式通常写在 CSS 里，正则在 JSX 标签内找不到。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Add hover state with visual change (background, border, scale)
### **Applies To**
  - *.tsx
  - *.jsx

## Missing Keyboard Focus Indicator

### **Id**
missing-focus-visible
### **Severity**
warning
### **Type**
regex
### **Pattern**
(outline:\s*none|outline:\s*0)(?![^{}]*:focus-visible)
### **Message**
Removed outline without focus-visible alternative. Keyboard/controller users can't see focus.
### **Fix Action**
Add :focus-visible style with visible indicator (outline, ring, glow)
### **Applies To**
  - *.css
  - *.scss
### **Test Cases**
  #### **Should Match**
    - outline: none;
    - outline: 0;
    - button { outline: none; } input:focus-visible { outline: 2px solid blue; }
  #### **Should Not Match**
    - .btn { outline: none; &:focus-visible { outline: 2px solid blue; } }

## Unity Canvas Without Scaler

### **Id**
unity-canvas-no-scaler
### **Severity**
warning
### **Type**
heuristic
### **Pattern**
Canvas[^}]*(?!CanvasScaler|ScaleWithScreenSize)
### **Message**
Unity Canvas may not have proper scaling for different resolutions.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：同一行已 AddComponent<CanvasScaler>() 时仍会命中。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Add CanvasScaler with Scale With Screen Size mode, reference 1920x1080
### **Applies To**
  - *.cs
  - *.unity

## Godot Control Fixed Size

### **Id**
godot-control-fixed-size
### **Severity**
warning
### **Type**
regex
### **Pattern**
custom_minimum_size\s*=\s*Vector2\s*\(\s*(?:[0-9]{3,}|[0-9]+\s*,\s*[0-9]{3,})
### **Message**
Large fixed minimum size (either axis) on Godot Control node. May not scale properly.
### **Fix Action**
Use anchors, grow directions, and size flags for responsive UI
### **Applies To**
  - *.tscn
  - *.tres
  - *.gd
### **Test Cases**
  #### **Should Match**
    - custom_minimum_size = Vector2(400, 200)
    - custom_minimum_size=Vector2( 320, 64 )
    - custom_minimum_size = Vector2(0, 168)
    - desc.custom_minimum_size = Vector2(360, 0)
  #### **Should Not Match**
    - custom_minimum_size = Vector2(64, 64)
    - custom_minimum_size = Vector2(0, 0)
    - custom_minimum_size = Vector2(99, 99)

## Missing Reduced Motion Check

### **Id**
no-reduced-motion-check
### **Severity**
info
### **Type**
heuristic
### **Pattern**
@keyframes|animation:|transition:[^}]*[5-9][0-9]{2}ms
### **Message**
Animations defined without checking prefers-reduced-motion.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：只要出现 @keyframes / animation: 就命中，根本没检查 prefers-reduced-motion。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Add @media (prefers-reduced-motion: reduce) to disable/reduce animations
### **Applies To**
  - *.css
  - *.scss

## Hardcoded Resolution Reference

### **Id**
hardcoded-resolution
### **Severity**
warning
### **Type**
regex
### **Pattern**
(?:resolution[^\n]*\b(?:1920|1080|2560|1440|3840|2160)\b|\b(?:1920|1080|2560|1440|3840|2160)\b[^\n]*resolution|screen(?:Width|Height)\s*=\s*(?:1920|1080))
### **Message**
Hardcoded resolution values. Should use dynamic screen dimensions.
### **Fix Action**
Use Screen.width/height or reference resolution with scaling
### **Applies To**
  - *.cs
  - *.gd
  - *.tsx
### **Test Cases**
  #### **Should Match**
    - const screenWidth = 1920;
    - if (resolution.x == 1920)
  #### **Should Not Match**
    - referenceResolution = new Vector2(1920, 1080);

## Static Button Text Instead of Localized

### **Id**
static-button-text
### **Severity**
info
### **Type**
regex
### **Pattern**
>["']?(OK|Cancel|Yes|No|Continue|Back|Exit|Quit|Save|Load)["']?<
### **Message**
Static button text. Consider localization support.
### **Fix Action**
Use localization keys: GetLocalizedString("ui_ok") or equivalent
### **Applies To**
  - *.tsx
  - *.jsx
  - *.xml
### **Test Cases**
  #### **Should Match**
    - <Button>OK</Button>
    - <button>Cancel</button>
  #### **Should Not Match**
    - <Button>{t('ok')}</Button>
    - <Button>确定</Button>

## Tooltip Without Delay

### **Id**
tooltip-no-delay
### **Severity**
info
### **Type**
heuristic
### **Pattern**
(onMouseEnter|onHover|@mouse_entered)[^}]*show.*[Tt]ooltip(?![^}]*delay|setTimeout|timer)
### **Message**
Tooltip appears immediately on hover. May flash during normal navigation.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：已用 setTimeout 延迟时仍会命中。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Add 300-500ms delay before showing tooltips
### **Applies To**
  - *.tsx
  - *.jsx
  - *.cs
  - *.gd

## Unity Find for UI Element

### **Id**
unity-find-ui-element
### **Severity**
warning
### **Type**
regex
### **Pattern**
GameObject\.Find\s*\([^)]*("Canvas"|"Button"|"Text"|"Image"|"Panel"|UI)
### **Message**
Using Find to locate UI elements. Cache references in Awake or use SerializeField.
### **Fix Action**
Use [SerializeField] private Button _button; and assign in Inspector
### **Applies To**
  - *.cs
### **Test Cases**
  #### **Should Match**
    - GameObject.Find("Canvas")
    - GameObject.Find("UIRoot")
  #### **Should Not Match**
    - GameObject.Find("Player")
    - transform.Find("Canvas")

## Unity UI Without Raycast Consideration

### **Id**
unity-ui-raycast-target
### **Severity**
info
### **Type**
heuristic
### **Pattern**
Image[^}]*(?!raycastTarget\s*=\s*false)
### **Message**
Image components default to raycastTarget=true. Disable on decorative images.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：已设 raycastTarget = false 时仍会命中。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Set raycastTarget=false on non-interactive images to improve performance
### **Applies To**
  - *.cs

## Godot UI Signal Emission Without Connection

### **Id**
godot-signal-not-connected
### **Severity**
info
### **Type**
heuristic
### **Pattern**
\.emit\s*\([^)]*\)(?![^}]*\.connect)
### **Message**
Signal emitted but connection not visible in same file. Ensure signal is connected.

**这条不是精确规则。** 它要判断的是「某处有 X 但别处没有 Y」这类跨作用域条件，正则表达不了：同文件已 .connect() 时仍会命中（断言范围不跨函数）。命中只说明该处值得人工看一眼，**不构成缺陷判定**；未命中也不代表没问题。
### **Fix Action**
Connect signals in _ready() or via editor
### **Applies To**
  - *.gd