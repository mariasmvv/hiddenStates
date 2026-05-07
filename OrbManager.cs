using UnityEngine;
using UnityEngine.UI;
using System.Collections;

/// <summary>
/// Attach to each Rock GameObject.
/// Handles visual feedback for mining attempts.
/// All reward/depletion logic lives in GameManager.
///
/// SETUP:
///   1. Attach to each rock GameObject
///   2. Set rockID = 0 on one, rockID = 1 on the other
///   3. Assign rockRenderer in Inspector (or leave blank — auto-finds)
///   4. Optionally assign rewardParticles, dustParticles
///   5. Make sure the rock has a Collider (Mesh Collider, Convex ticked)
///   6. Set GameObject tag to "Rock"
///
///   The progress bar canvas is created automatically above the rock.
///   No manual UI setup required.
/// </summary>
public class OrbManager : MonoBehaviour
{
    // ─────────────────────────────────────────
    //  Inspector
    // ─────────────────────────────────────────
    [Header("Identity")]
    public int rockID = 0;

    [Header("Visuals")]
    public Renderer rockRenderer;
    public Color baseColor     = new Color(0.6f,  0.55f, 0.5f);
    public Color rewardColor   = new Color(1f,    0.85f, 0.1f);
    public Color noRewardColor = new Color(0.35f, 0.35f, 0.35f);
    public float flashDuration = 0.4f;

    // [Header("Effects")]
// public GameObject rewardParticles;
// public GameObject dustParticles;

    [Header("Progress Bar")]
    [Tooltip("How high above the rock centre the progress bar floats (metres)")]
    public float progressBarHeight = 1.2f;

    [Tooltip("Diameter of the radial progress bar in world units")]
    public float progressBarSize = 0.3f;

    [Header("Cooldown")]
    public float cooldownDuration = 1.0f;

    // ─────────────────────────────────────────
    //  Hidden State — set by GameManager only
    // ─────────────────────────────────────────
    private bool isActive = false;

    // ─────────────────────────────────────────
    //  Runtime State
    // ─────────────────────────────────────────
    private bool      isOnCooldown  = false;
    private Coroutine flashCoroutine;

    // ─────────────────────────────────────────
    //  Progress Bar (auto-built)
    // ─────────────────────────────────────────
    private GameObject barCanvasGO;
    private Image      barFill;
    private Image      barBg;

    // ─────────────────────────────────────────
    //  Unity Lifecycle
    // ─────────────────────────────────────────
    void Start()
    {
        if (rockRenderer == null)
            rockRenderer = GetComponent<Renderer>();
        if (rockRenderer == null)
            rockRenderer = GetComponentInChildren<Renderer>();

        SetBaseVisual();
        BuildProgressBar();
        HideProgressBar();
    }

    // ─────────────────────────────────────────
    //  Auto-build World Space Progress Bar
    //  Simple horizontal bar — no sprite required, works on all Unity versions.
    // ─────────────────────────────────────────
    private void BuildProgressBar()
{
    // 1. Canvas Setup
    barCanvasGO = new GameObject($"Rock{rockID}_ProgressCanvas");
    barCanvasGO.transform.SetParent(transform);
    barCanvasGO.transform.localPosition = Vector3.up * progressBarHeight;
    barCanvasGO.transform.localRotation = Quaternion.identity;

    Canvas canvas = barCanvasGO.AddComponent<Canvas>();
    canvas.renderMode = RenderMode.WorldSpace;

    RectTransform canvasRT = barCanvasGO.GetComponent<RectTransform>();
    canvasRT.sizeDelta = new Vector2(200f, 20f);
    float s = progressBarSize / 200f;
    barCanvasGO.transform.localScale = new Vector3(s, s, s);

    // 2. CREATE SHARP PIXEL SPRITE (Fixes the "fading edges" look)
    Texture2D tex = new Texture2D(1, 1);
    tex.SetPixel(0, 0, Color.white);
    tex.Apply();
    Sprite pixelSprite = Sprite.Create(tex, new Rect(0, 0, 1, 1), new Vector2(0.5f, 0.5f));

    // 3. Dark Background Track (The Size Comparison Bar)
    GameObject bgGO = new GameObject("BarBg", typeof(RectTransform), typeof(Image));
    bgGO.transform.SetParent(barCanvasGO.transform, false);
    RectTransform bgRT = bgGO.GetComponent<RectTransform>();
    bgRT.anchorMin = Vector2.zero;
    bgRT.anchorMax = Vector2.one;
    bgRT.offsetMin = Vector2.zero;
    bgRT.offsetMax = Vector2.zero;
    
    barBg = bgGO.GetComponent<Image>();
    barBg.sprite = pixelSprite; // Using sharp sprite
    barBg.color = new Color(1f, 1f, 1f, 0.12f); // Matching your UI faint gray

    // 4. Yellow Fill Bar (The solid growing bar)
    GameObject fillGO = new GameObject("BarFill", typeof(RectTransform), typeof(Image));
    fillGO.transform.SetParent(bgGO.transform, false);
    RectTransform fillRT = fillGO.GetComponent<RectTransform>();
    
    // Stretch to match background exactly
    fillRT.anchorMin = Vector2.zero;
    fillRT.anchorMax = Vector2.one;
    fillRT.offsetMin = Vector2.zero;
    fillRT.offsetMax = Vector2.zero;
    
    barFill = fillGO.GetComponent<Image>();
    barFill.sprite = pixelSprite; // Using sharp sprite
    barFill.color = new Color(1f, 0.85f, 0f, 1f); // Solid Gold
    barFill.type = Image.Type.Filled;
    barFill.fillMethod = Image.FillMethod.Horizontal;
    barFill.fillOrigin = (int)Image.OriginHorizontal.Left;
    barFill.fillAmount = 0f;

    barCanvasGO.AddComponent<BillboardToCamera>();
}

    // ─────────────────────────────────────────
    //  Called by GameManager
    // ─────────────────────────────────────────
    public void SetActiveState(bool active, float rewardProbability, float depletionProbability)
    {
        isActive = active;
    }

    // ─────────────────────────────────────────
    //  Called by VRPickaxe
    // ─────────────────────────────────────────
    public bool TryHit() => !isOnCooldown;

    public void PlayFeedback(bool rewarded)
    {
        if (flashCoroutine != null)
            StopCoroutine(flashCoroutine);
        flashCoroutine = StartCoroutine(FlashFeedback(rewarded));
    }

    // ─────────────────────────────────────────
    //  Progress Bar
    // ─────────────────────────────────────────
    public void UpdateProgressBar(float t)
{
    if (barCanvasGO == null) return;
    barCanvasGO.SetActive(true);

    t = Mathf.Clamp01(t);
    
    if (barFill != null)
    {
        // Physically grow the bar
        barFill.fillAmount = t;
        
        // KEEP COLOR SOLID: Removed Lerp to maintain constant intensity
        barFill.color = new Color(1f, 0.85f, 0f, 1f); 
    }
}

    public void HideProgressBar()
    {
        if (barCanvasGO == null) return;
        barCanvasGO.SetActive(false);
        if (barFill != null) barFill.fillAmount = 0f;
    }

    // ─────────────────────────────────────────
    //  Flash Feedback
    // ─────────────────────────────────────────
    private IEnumerator FlashFeedback(bool rewarded)
{
    isOnCooldown = true;

    // --- REMOVED PARTICLE LOGIC ---
    /* GameObject prefabToSpawn = rewarded ? rewardParticles : dustParticles;
    if (prefabToSpawn != null)
    {
        GameObject effectInstance = Instantiate(prefabToSpawn, transform.position, Quaternion.identity);
        Destroy(effectInstance, 3.0f);
    }
    */
    // ------------------------------

    // Keep the color flash so the player knows the mine was successful
    SetColor(rewarded ? rewardColor : noRewardColor);
    yield return new WaitForSeconds(flashDuration);
    SetBaseVisual();

    float remaining = cooldownDuration - flashDuration;
    if (remaining > 0f)
        yield return new WaitForSeconds(remaining);

    isOnCooldown = false;
}

    // ─────────────────────────────────────────
    //  Helpers
    // ─────────────────────────────────────────
    private void SetBaseVisual() => SetColor(baseColor);

    private void SetColor(Color color)
    {
        if (rockRenderer != null)
            rockRenderer.material.color = color;
    }

    public bool IsOnCooldown => isOnCooldown;
    public bool IsActive     => isActive;
}

// ─────────────────────────────────────────
//  Billboard — progress bar always faces the XR camera
// ─────────────────────────────────────────
public class BillboardToCamera : MonoBehaviour
{
    private Camera _cam;

    void Start()
    {
        _cam = Camera.main;
        if (_cam == null)
            _cam = FindObjectOfType<Camera>();
    }

    void LateUpdate()
    {
        if (_cam == null) return;
        transform.LookAt(transform.position + _cam.transform.rotation * Vector3.forward,
                         _cam.transform.rotation * Vector3.up);
    }
}