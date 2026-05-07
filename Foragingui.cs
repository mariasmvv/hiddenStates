using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections;

/// <summary>
/// VR World Space HUD for the Rustbucket foraging task.
///
/// SETUP:
///   1. Create a Canvas GameObject
///   2. Set Canvas Render Mode to WORLD SPACE
///   3. Set Canvas width=600, height=200, scale=0.002
///   4. Parent it to XR Origin so it moves with the player
///   5. Set local position to (0, 0, 2) — 2m in front of player
///   6. Attach this script to the Canvas
///   7. All UI elements are created automatically at runtime
///
/// LAYOUT:
///  ┌─────────────────────────────────────────┐
///  │        [TIMER  —  top centre]           │
///  │  [LEVEL — top left]  [GOLD — top right] │
///  │            [progress bar]               │
///  │          [MESSAGE — centre]             │
///  │       [REWARD BURST — centre]           │
///  └─────────────────────────────────────────┘
/// </summary>
public class ForagingUI : MonoBehaviour
{
    // ─────────────────────────────────────────
    //  Runtime References
    // ─────────────────────────────────────────
    private TMP_Text timerText;
    private TMP_Text levelText;
    private TMP_Text goldText;
    private TMP_Text messageText;
    private TMP_Text rewardText;
    private GameObject messagePanel;
    private GameObject rewardPanel;
    private RectTransform rewardRect;

    private GameObject timerPanel;
    private GameObject levelPanel;
    private GameObject goldPanel;

    public bool isPracticeMode = false;

    // ─── Gold Progress Bar ────────────────────────
    private Image      goldBarFill;
    private GameObject goldBarPanel;

    [Header("Gold Progress Bar")]
    [Tooltip("Total gold target displayed in the progress bar. Set to match your session's expected gold ceiling.")]
    public float goldTargetAmount = 500f;

    // ─────────────────────────────────────────
    //  Style
    // ─────────────────────────────────────────
    private static readonly Color BgColor      = new Color(0f,    0f,    0f,    0.55f);
    // Change these lines in the Style section
    private static readonly Color GoldColor = new Color(0.85f, 0.75f, 0.85f, 1f); // Approx D8BFD8
    private static readonly Color RewardBg  = new Color(0.85f, 0.75f, 0.85f, 0.92f);
    private static readonly Color TextColor    = new Color(0.95f, 0.95f, 0.95f, 1f);
    private static readonly Color TimerColor   = new Color(1f,    1f,    1f,    1f);
    private static readonly Color TimerUrgent  = new Color(1f,    0.3f,  0.2f,  1f);
    private static readonly Color RewardText   = new Color(0.55f, 0f, 0.55f, 1f);

    // ─────────────────────────────────────────
    //  Unity Lifecycle
    // ─────────────────────────────────────────
    void Awake()
    {
        BuildHUD();
    }

    void Start() {
    if (isPracticeMode) {
        // Hide the "Scary" experimental stuff
        if (timerText != null) timerText.gameObject.SetActive(false);
        if (levelText != null) levelText.gameObject.SetActive(false);
        if (goldText != null) goldText.gameObject.SetActive(false);
        if (goldBarPanel != null) goldBarPanel.SetActive(false);
        if (timerPanel != null) timerPanel.SetActive(false);
        if (levelPanel != null) levelPanel.SetActive(false);
        if (goldPanel != null) goldPanel.SetActive(false);

        }
    }
    // ─────────────────────────────────────────
    //  HUD Construction
    // ─────────────────────────────────────────
    private void BuildHUD()
    {
        // ── Timer — top centre ───────────────
        timerPanel = CreatePanel("TimerPanel",
            new Vector2(0.5f, 1f), new Vector2(0.5f, 1f),
            new Vector2(0.5f, 1f), new Vector2(0f, -10f),
            new Vector2(220f, 60f));
        timerText = AddText(timerPanel, "5:00", 32,
            TextAlignmentOptions.Center, TimerColor);

        // ── Level — top left ─────────────────
        levelPanel = CreatePanel("LevelPanel",
            new Vector2(0f, 1f), new Vector2(0f, 1f),
            new Vector2(0f, 1f), new Vector2(10f, -10f),
            new Vector2(180f, 52f));
        levelText = AddText(levelPanel, "Level 1 / 5", 20,
            TextAlignmentOptions.Left, GoldColor);

        // ── Gold — top right ─────────────────
        goldPanel = CreatePanel("GoldPanel",
            new Vector2(1f, 1f), new Vector2(1f, 1f),
            new Vector2(1f, 1f), new Vector2(-10f, -10f),
            new Vector2(180f, 52f));
        goldText = AddText(goldPanel, "Gold: 0", 20,
            TextAlignmentOptions.Right, GoldColor);

        // ── Message — centre ─────────────────
        messagePanel = CreatePanel("MessagePanel",
            new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
            new Vector2(0.5f, 0.5f), new Vector2(0f, -30f),
            new Vector2(500f, 70f));
        messageText = AddText(messagePanel, "", 24,
            TextAlignmentOptions.Center, TextColor);
        messagePanel.SetActive(false);

        // ── Reward Burst — centre above message ──
        rewardPanel = CreatePanel("RewardPanel",
            new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
            new Vector2(0.5f, 0.5f), new Vector2(0f, 20f),
            new Vector2(420f, 90f));
        rewardPanel.GetComponent<Image>().color = RewardBg;
        rewardText = AddText(rewardPanel, "", 40,
            TextAlignmentOptions.Center, RewardText);
        rewardRect = rewardPanel.GetComponent<RectTransform>();
        rewardPanel.SetActive(false);

        BuildGoldBar();

        
    }

    public void UpdateResourceLabel(string resourceName = "Gold", float amount = 0f)
{
    if (goldText != null)
        goldText.text = $"{resourceName}: {amount:F0}";
}

    // ─────────────────────────────────────────
//  Gold Progress Bar
// ─────────────────────────────────────────
private void BuildGoldBar()
{
    // 1. Main Panel: Now anchored to TOP (0.5f, 1f) so it stays under the Timer
    // Lowered it to y: -80 to sit below the Top Centre Timer
    goldBarPanel = CreatePanel("GoldBarPanel",
        new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), 
        new Vector2(0.5f, 1f), new Vector2(0f, -80f), 
        new Vector2(400f, 60f)); 

    Texture2D tex = new Texture2D(1, 1);
    tex.SetPixel(0, 0, Color.white);
    tex.Apply();
    Sprite pixelSprite = Sprite.Create(tex, new Rect(0, 0, 1, 1), new Vector2(0.5f, 0.5f));

    // 2. Background Track
    GameObject bgGO = new GameObject("GoldBarBg", typeof(RectTransform), typeof(Image));
    bgGO.transform.SetParent(goldBarPanel.transform, false);
    RectTransform bgRT = bgGO.GetComponent<RectTransform>();
    
    bgRT.anchorMin = new Vector2(0.5f, 0.5f);
    bgRT.anchorMax = new Vector2(0.5f, 0.5f);
    bgRT.pivot = new Vector2(0.5f, 0.5f);
    bgRT.sizeDelta = new Vector2(380f, 18f); 
    bgRT.anchoredPosition = new Vector2(0f, -5f); // Centred in panel
    
    Image bgImage = bgGO.GetComponent<Image>();
    bgImage.sprite = pixelSprite;
    bgImage.color = new Color(1f, 1f, 1f, 0.12f);

    // 3. Yellow Fill
    GameObject fillGO = new GameObject("GoldBarFill", typeof(RectTransform), typeof(Image));
    fillGO.transform.SetParent(bgGO.transform, false);
    RectTransform fillRT = fillGO.GetComponent<RectTransform>();
    fillRT.anchorMin = Vector2.zero;
    fillRT.anchorMax = Vector2.one;
    fillRT.offsetMin = Vector2.zero;
    fillRT.offsetMax = Vector2.zero;

    goldBarFill = fillGO.GetComponent<Image>();
    goldBarFill.sprite = pixelSprite;
    goldBarFill.color = new Color(0.85f, 0.75f, 0.85f, 1f);
    goldBarFill.type = Image.Type.Filled;
    goldBarFill.fillMethod = Image.FillMethod.Horizontal;
    goldBarFill.fillOrigin = (int)Image.OriginHorizontal.Left;
    goldBarFill.fillAmount = 0f; 
}

public void UpdateGoldBar(float totalGold)
{
    if (goldBarFill == null) return;

    float ratio = goldTargetAmount > 0 ? (totalGold / goldTargetAmount) : 0f;
    
    // Hard set the fill amount
    goldBarFill.fillAmount = Mathf.Clamp01(ratio);
}
    // ─────────────────────────────────────────
    //  Helpers
    // ─────────────────────────────────────────
    private GameObject CreatePanel(string name,
        Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot,
        Vector2 offset, Vector2 size)
    {
        GameObject obj = new GameObject(name,
            typeof(RectTransform), typeof(Image));
        obj.transform.SetParent(transform, false);

        RectTransform rt    = obj.GetComponent<RectTransform>();
        rt.anchorMin        = anchorMin;
        rt.anchorMax        = anchorMax;
        rt.pivot            = pivot;
        rt.anchoredPosition = offset;
        rt.sizeDelta        = size;

        obj.GetComponent<Image>().color = BgColor;
        return obj;
    }

    private TMP_Text AddText(GameObject parent, string defaultText,
        float fontSize, TextAlignmentOptions alignment, Color color)
    {
        GameObject obj = new GameObject("Text", typeof(RectTransform));
        obj.transform.SetParent(parent.transform, false);

        RectTransform rt = obj.GetComponent<RectTransform>();
        rt.anchorMin     = Vector2.zero;
        rt.anchorMax     = Vector2.one;
        rt.offsetMin     = new Vector2(8f,  4f);
        rt.offsetMax     = new Vector2(-8f, -4f);

        TMP_Text t   = obj.AddComponent<TextMeshProUGUI>();
        t.text       = defaultText;
        t.fontSize   = fontSize;
        t.color      = color;
        t.alignment  = alignment;
        t.fontStyle  = FontStyles.Bold;
        return t;
    }

    // ─────────────────────────────────────────
    //  Public API
    // ─────────────────────────────────────────

    /// <summary>Updates the countdown timer. Turns red under 30s.</summary>
    public void UpdateTimer(float secondsRemaining)
    {
        if (timerText == null) return;
        int mins = Mathf.FloorToInt(secondsRemaining / 60f);
        int secs = Mathf.FloorToInt(secondsRemaining % 60f);
        timerText.text  = $"{mins}:{secs:D2}";
        timerText.color = secondsRemaining <= 30f ? TimerUrgent : TimerColor;
    }

    /// <summary>Updates the level label — e.g. "Level 2 / 5"</summary>
    public void UpdateLevel(int level)
    {
        if (levelText != null)
            levelText.text = $"Level {level} / 5";
    }

    /// <summary>Updates the gold counter</summary>
    public void UpdateGold(float gold)
    {
        if (goldText != null)
            goldText.text = $"Gold: {gold:F0}";
    }

    /// <summary>
    /// Shows a plain centre message.
    /// duration = 0 keeps it visible indefinitely.
    /// </summary>
    private Coroutine messageCoroutine;

    public void ShowMessage(string message, float duration = 2f)
    {
        if (messagePanel == null || messageText == null) return;

        if (messageCoroutine != null)
            StopCoroutine(messageCoroutine);

        messageText.text = message;
        messagePanel.SetActive(true);

        if (duration > 0f)
            messageCoroutine = StartCoroutine(HideAfter(messagePanel, duration));
    }

    private IEnumerator HideAfter(GameObject panel, float delay)
    {
        yield return new WaitForSeconds(delay);
        if (panel != null) panel.SetActive(false);
    }

    /// <summary>
    /// Exciting animated gold reward burst.
    /// Shows a large gold panel that punches in, holds, then fades out.
    /// totalGold is shown as a running total underneath.
    /// </summary>
    private Coroutine rewardCoroutine;

    public void ShowRewardMessage(string gainText, float totalGold)
    {
        if (rewardPanel == null || rewardText == null) return;

        if (rewardCoroutine != null)
            StopCoroutine(rewardCoroutine);

        rewardText.text = $"{gainText}\n<size=22><color=#8B008B>Total: {totalGold:F0}</color></size>";
        rewardCoroutine = StartCoroutine(RewardBurst());
    }

    private IEnumerator RewardBurst()
    {
        rewardPanel.SetActive(true);

        // Punch in — scale from 0.4 → 1.15 → 1.0
        float t = 0f;
        float punchIn = 0.12f;
        while (t < punchIn)
        {
            t += Time.deltaTime;
            float s = Mathf.Lerp(0.4f, 1.15f, t / punchIn);
            rewardRect.localScale = new Vector3(s, s, 1f);
            yield return null;
        }

        // Settle — scale from 1.15 → 1.0
        t = 0f;
        float settle = 0.08f;
        while (t < settle)
        {
            t += Time.deltaTime;
            float s = Mathf.Lerp(1.15f, 1.0f, t / settle);
            rewardRect.localScale = new Vector3(s, s, 1f);
            yield return null;
        }
        rewardRect.localScale = Vector3.one;

        // Hold
        yield return new WaitForSeconds(1.0f);

        // Fade out — shrink and fade alpha
        Image img   = rewardPanel.GetComponent<Image>();
        Color bgCol = RewardBg;
        Color txCol = RewardText;
        t = 0f;
        float fadeOut = 0.3f;
        while (t < fadeOut)
        {
            t += Time.deltaTime;
            float a = Mathf.Lerp(1f, 0f, t / fadeOut);
            float s = Mathf.Lerp(1f, 0.85f, t / fadeOut);
            if (img != null) img.color = new Color(bgCol.r, bgCol.g, bgCol.b, bgCol.a * a);
            if (rewardText != null) rewardText.color = new Color(txCol.r, txCol.g, txCol.b, a);
            rewardRect.localScale = new Vector3(s, s, 1f);
            yield return null;
        }

        rewardPanel.SetActive(false);

        // Reset colors and scale for next time
        if (img != null) img.color = RewardBg;
        if (rewardText != null) rewardText.color = RewardText;
        rewardRect.localScale = Vector3.one;
    }
}