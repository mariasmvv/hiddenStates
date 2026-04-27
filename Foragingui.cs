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

    // ─────────────────────────────────────────
    //  Style
    // ─────────────────────────────────────────
    private static readonly Color BgColor      = new Color(0f,    0f,    0f,    0.55f);
    private static readonly Color RewardBg     = new Color(0.9f,  0.65f, 0f,    0.92f);
    private static readonly Color TextColor    = new Color(0.95f, 0.95f, 0.95f, 1f);
    private static readonly Color GoldColor    = new Color(1f,    0.85f, 0.1f,  1f);
    private static readonly Color TimerColor   = new Color(1f,    1f,    1f,    1f);
    private static readonly Color TimerUrgent  = new Color(1f,    0.3f,  0.2f,  1f);
    private static readonly Color RewardText   = new Color(1f,    1f,    0.85f, 1f);

    // ─────────────────────────────────────────
    //  Unity Lifecycle
    // ─────────────────────────────────────────
    void Awake()
    {
        BuildHUD();
    }

    // ─────────────────────────────────────────
    //  HUD Construction
    // ─────────────────────────────────────────
    private void BuildHUD()
    {
        // ── Timer — top centre ───────────────
        GameObject timerPanel = CreatePanel("TimerPanel",
            new Vector2(0.5f, 1f), new Vector2(0.5f, 1f),
            new Vector2(0.5f, 1f), new Vector2(0f, -10f),
            new Vector2(220f, 60f));
        timerText = AddText(timerPanel, "5:00", 32,
            TextAlignmentOptions.Center, TimerColor);

        // ── Level — top left ─────────────────
        GameObject levelPanel = CreatePanel("LevelPanel",
            new Vector2(0f, 1f), new Vector2(0f, 1f),
            new Vector2(0f, 1f), new Vector2(10f, -10f),
            new Vector2(180f, 52f));
        levelText = AddText(levelPanel, "Level 1 / 5", 20,
            TextAlignmentOptions.Left, GoldColor);

        // ── Gold — top right ─────────────────
        GameObject goldPanel = CreatePanel("GoldPanel",
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
    public void UpdateLevel(int level, int totalLevels)
    {
        if (levelText != null)
            levelText.text = $"Level {level} / {totalLevels}";
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

        rewardText.text = $"★  {gainText}  ★\n<size=22><color=#FFD700>Total: {totalGold:F0}</color></size>";
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