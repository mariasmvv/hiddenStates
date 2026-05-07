using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using System.Collections;

[RequireComponent(typeof(UnityEngine.XR.Interaction.Toolkit.Interactables.XRGrabInteractable))]
[RequireComponent(typeof(Rigidbody))]
public class VRPickaxe : MonoBehaviour
{
    // ─────────────────────────────────────────
    //  Inspector — Hand References
    // ─────────────────────────────────────────
    [Header("Hand References")]
    public Transform leftHandController;
    public Transform rightHandController;

    // ─────────────────────────────────────────
    //  Inspector — Mining Aim
    // ─────────────────────────────────────────
    [Header("Mining Aim")]
    public float miningRange = 3f;

    // ─────────────────────────────────────────
    //  Inspector — Rock Targets
    // ─────────────────────────────────────────
    [Header("Rock Targets")]
    public Transform rock0Transform;
    public Transform rock1Transform;

    // ─────────────────────────────────────────
    //  Inspector — Timings
    // ─────────────────────────────────────────
    [Header("Timings (seconds)")]
    public float miningDuration = 2f;
    public float axeCooldownDuration = 5f;
    public float floatBackSpeed = 2f;

    // ─────────────────────────────────────────
    //  Inspector — Swing Animation
    // ─────────────────────────────────────────
    [Header("Swing Animation")]
    public float swingMaxAngle = 60f;
    public float swingBackAngle = 30f;
    public float swingSpeed = 5f;
    public float returnSpeed = 8f;

    // ─────────────────────────────────────────
    //  Inspector — Visuals
    // ─────────────────────────────────────────
    [Header("Axe Cooldown Visuals")]
    public Color cooldownColor = new Color(1f, 0.15f, 0.1f);
    public Color readyColor = new Color(1f, 1f, 1f);

    // ─────────────────────────────────────────
    //  Inspector — Axe Mesh Child
    // ─────────────────────────────────────────
    [Header("Axe Mesh (swing target)")]
    public Transform axeMesh;

    // ─────────────────────────────────────────
    //  Runtime State
    // ─────────────────────────────────────────
    [Header("Runtime State (read-only)")]
    [SerializeField] private bool isHeld = false;
    [SerializeField] private bool isMining = false;
    [SerializeField] private bool isAimingAtRock = false;
    [SerializeField] private bool isOnAxeCooldown = false;
    [SerializeField] private bool isFloatingBack = false;
    [SerializeField] private float miningProgress = 0f;
    [SerializeField] private float axeCooldownTimer = 0f;
    [SerializeField] private int activeRockID = -1;
    [SerializeField] private bool isRightHand = false;

    // ─────────────────────────────────────────
    //  Internal
    // ─────────────────────────────────────────
    private Vector3 spawnPosition;
    private Quaternion spawnRotation;
    private Quaternion meshBaseLocalRotation;
    private float swingAngle = 0f;

    private UnityEngine.XR.Interaction.Toolkit.Interactables.XRGrabInteractable grabInteractable;
    private Rigidbody rb;
    private Renderer axeRenderer;
    private LineRenderer laserLine;
    private GameManager gameManager;
    private ForagingUI ui;
    private Transform activeHand;

    private OrbManager rock0;
    private OrbManager rock1;
    private OrbManager currentRock;

    // ─────────────────────────────────────────
    //  Unity Lifecycle
    // ─────────────────────────────────────────
    void Awake()
    {
        // REMOVED: DontDestroyOnLoad(gameObject); 
        // By removing the above, we prevent the "Multiplier" lag.

        grabInteractable = GetComponent<UnityEngine.XR.Interaction.Toolkit.Interactables.XRGrabInteractable>();
        rb = GetComponent<Rigidbody>();
        axeRenderer = GetComponentInChildren<Renderer>();
        
        // We find these in Awake/Start because the Managers are persistent
        gameManager = FindObjectOfType<GameManager>();
        ui = FindObjectOfType<ForagingUI>();

        if (gameManager == null)
            Debug.LogWarning("[VRPickaxe] GameManager not found! This is normal if starting from Level 2+ for testing.");
    }

    void Start()
    {
        spawnPosition = transform.position;
        spawnRotation = transform.rotation;

        if (axeMesh == null && transform.childCount > 0)
            axeMesh = transform.GetChild(0);
        
        meshBaseLocalRotation = axeMesh != null ? axeMesh.localRotation : Quaternion.identity;

        // CRITICAL: This finds the rocks in the CURRENT scene
        RefreshRockReferences();

        rb.isKinematic = true;

        grabInteractable.selectEntered.AddListener(OnGrabbed);
        grabInteractable.selectExited.AddListener(OnReleased);

        SetAxeColor(readyColor);
        BuildLaserLine();
    }

    private void RefreshRockReferences()
    {
        rock0 = null;
        rock1 = null;

        foreach (var r in FindObjectsOfType<OrbManager>())
        {
            if (r.rockID == 0) rock0 = r;
            if (r.rockID == 1) rock1 = r;
        }

        if (rock0 != null) rock0Transform = rock0.transform;
        if (rock1 != null) rock1Transform = rock1.transform;
    }

    // ─────────────────────────────────────────
    //  Laser Line
    // ─────────────────────────────────────────
    private void BuildLaserLine()
    {
        laserLine = gameObject.AddComponent<LineRenderer>();
        laserLine.positionCount = 2;
        laserLine.startWidth = 0.005f;
        laserLine.endWidth = 0.002f;
        laserLine.useWorldSpace = true;
        laserLine.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        laserLine.receiveShadows = false;
        laserLine.material = new Material(Shader.Find("Sprites/Default"));
        SetLaserColor(Color.red);
        laserLine.enabled = false;
    }

    private void SetLaserColor(Color c)
    {
        if (laserLine == null) return;
        laserLine.startColor = c;
        laserLine.endColor = new Color(c.r, c.g, c.b, 0f);
    }

    private void UpdateLaser(bool aimed)
    {
        if (laserLine == null) return;
        laserLine.SetPosition(0, transform.position);
        laserLine.SetPosition(1, transform.position + transform.forward * miningRange);
        SetLaserColor(aimed ? Color.green : Color.red);
    }

    // ─────────────────────────────────────────
    //  Update Loop
    // ─────────────────────────────────────────
 void Update()
{
    if (isFloatingBack) { FloatBack(); return; }
    if (isOnAxeCooldown) { TickAxeCooldown(); return; }
    if (!isHeld) return;

    // FIX: Only check sessionActive if we are NOT in the intro
    bool isIntro = UnityEngine.SceneManagement.SceneManager.GetActiveScene().buildIndex == 0;
    if (!isIntro)
    {
        if (gameManager != null && !gameManager.IsSessionActive) return;
    }

    HandleMiningAim();
    AnimateSwing();
}
    // ─────────────────────────────────────────
    //  Grab / Release
    // ─────────────────────────────────────────
    private void OnGrabbed(SelectEnterEventArgs args)
    {
        // Re-find references just in case of scene transition timing
        if (gameManager == null) gameManager = FindObjectOfType<GameManager>();
        if (ui == null) ui = FindObjectOfType<ForagingUI>();
        
        // Ensure the rock we are grabbing for is still valid
        RefreshRockReferences();

        if (isOnAxeCooldown)
        {
            grabInteractable.interactionManager.CancelInteractorSelection(
                args.interactorObject as UnityEngine.XR.Interaction.Toolkit.Interactors.IXRSelectInteractor
            );
            ui?.ShowMessage("Axe cooling down...", 1f);
            return;
        }

        isHeld = true;
        miningProgress = 0f;
        isMining = false;
        activeHand = args.interactorObject.transform;

        isRightHand = IsRightHand(activeHand);
        activeRockID = isRightHand ? 0 : 1;
        currentRock = isRightHand ? rock0 : rock1;

        if (laserLine != null) laserLine.enabled = true;

        gameManager?.LogExternalEvent(
            "axe_pickup",
            $"hand={(isRightHand ? "right" : "left")};rockAssigned={activeRockID}"
        );

        string rockLabel = isRightHand ? "right rock" : "left rock";
        ui?.ShowMessage($"Point axe at {rockLabel} to mine", 2f);
    }

    private void OnReleased(SelectExitEventArgs args)
    {
        isHeld = false;
        isMining = false;
        isAimingAtRock = false;
        miningProgress = 0f;
        activeHand = null;

        if (laserLine != null) laserLine.enabled = false;
        if (currentRock != null) currentRock.HideProgressBar();

        currentRock = null;
        activeRockID = -1;

        gameManager?.LogExternalEvent("axe_drop", "");

        StartAxeCooldown();

        Debug.Log("[VRPickaxe] Released.");
    }

    // ─────────────────────────────────────────
    //  Mining — Laser Aim Detection
    // ─────────────────────────────────────────
    // Inside VRPickaxe.cs -> HandleMiningAim()
private void HandleMiningAim()
{
    if (currentRock == null) return;

    if (currentRock.IsOnCooldown)
    {
        isMining = false;
        miningProgress = 0f;
        currentRock.HideProgressBar();
        UpdateLaser(false);
        return; 
    }

    Ray ray = new Ray(transform.position, transform.forward);
    bool hitThisRock = false;

    if (Physics.Raycast(ray, out RaycastHit hit, miningRange))
    {
        OrbManager hitOrb = hit.collider.GetComponent<OrbManager>();
        if (hitOrb == null) hitOrb = hit.collider.GetComponentInParent<OrbManager>();
        
        // This is the "Recognition" part
        hitThisRock = hitOrb != null && hitOrb == currentRock;
    }

    isAimingAtRock = hitThisRock;
    UpdateLaser(hitThisRock);

    if (isAimingAtRock)
    {
        if (!isMining)
        {
            isMining = true;
            miningProgress = 0f;
        }

        miningProgress += Time.deltaTime / miningDuration;
        miningProgress = Mathf.Clamp01(miningProgress);
        currentRock.UpdateProgressBar(miningProgress);

        if (miningProgress >= 1f)
        {
            // CHANGE THIS LINE: Redirect to a new local method
            ResolveMiningResolution(); 
            isMining = false;
            miningProgress = 0f;
        }
    }
}

    // ─────────────────────────────────────────
    //  Swing Animation
    // ─────────────────────────────────────────
    private void AnimateSwing()
    {
        if (axeMesh == null) return;

        if (!isMining)
        {
            swingAngle = Mathf.Lerp(swingAngle, 0f, returnSpeed * Time.deltaTime);
            axeMesh.localRotation = meshBaseLocalRotation * Quaternion.Euler(0f, 270f, swingAngle);
            return;
        }

        Transform target = isRightHand ? rock0Transform : rock1Transform;
        float rockAngleOffset = 0f;
        if (target != null)
        {
            Vector3 toRock = (target.position - transform.position).normalized;
            float dot = Vector3.Dot(transform.forward, toRock);
            rockAngleOffset = (1f - dot) * 15f;
        }

        float speed = swingSpeed * (1f + miningProgress * 0.5f);
        float forward = swingMaxAngle + rockAngleOffset;
        float back = -swingBackAngle;
        float t = (Mathf.Sin(Time.time * speed) + 1f) * 0.5f;
        swingAngle = Mathf.Lerp(back, forward, t);

        axeMesh.localRotation = meshBaseLocalRotation * Quaternion.Euler(0f, 270f, swingAngle);
    }

private void ResolveMiningResolution()
{
    if (currentRock == null) return;
    if (!currentRock.TryHit()) return;

    // Check if we are in the Intro (Scene 0)
    if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().buildIndex == 0)
    {
        PracticeManager pm = FindObjectOfType<PracticeManager>();
        if (pm != null)
        {
            // FIX: Pass activeRockID (int) instead of isRightHand (bool)
            pm.ResolvePracticeHit(activeRockID); 
            currentRock.PlayFeedback(true); 
        }
    }
    else
    {
        // Real game logic for Level 1-5
        if (gameManager == null) gameManager = FindObjectOfType<GameManager>();
        
        MiningResult result = gameManager.ResolveMiningAttempt(activeRockID);
        currentRock.PlayFeedback(result.rewarded);

        if (result.rewarded)
        {
            string resource = gameManager.CurrentResourceName; 
            ui?.ShowRewardMessage($"+{result.goldGained:F0} {resource}!", gameManager.TotalGold);
            
            ui?.UpdateGoldBar(gameManager.TotalGold);
        }
        else
        {
            ui?.ShowMessage("Nothing... try again or switch rocks!", 1.5f);
        }
    }
}

    // ─────────────────────────────────────────
    //  Axe Cooldown
    // ─────────────────────────────────────────
    private void StartAxeCooldown()
    {
        isOnAxeCooldown = true;
        axeCooldownTimer = axeCooldownDuration;
        isFloatingBack = true;
        grabInteractable.enabled = false;
        SetAxeColor(cooldownColor);
    }

    private void TickAxeCooldown()
    {
        axeCooldownTimer -= Time.deltaTime;

        float pulse = (Mathf.Sin(Time.time * 4f) + 1f) / 2f;
        SetAxeColor(Color.Lerp(new Color(0.3f, 0f, 0f), cooldownColor, pulse));

        if (axeCooldownTimer <= 0f)
        {
            isOnAxeCooldown = false;
            grabInteractable.enabled = true;
            SetAxeColor(readyColor);
            ui?.ShowMessage("Axe ready!", 2f);
            Debug.Log("[VRPickaxe] Axe ready.");
        }
    }

    // ─────────────────────────────────────────
    //  Float Back
    // ─────────────────────────────────────────
    private void FloatBack()
    {
        rb.isKinematic = true;

        transform.position = Vector3.Lerp(
            transform.position, spawnPosition, floatBackSpeed * Time.deltaTime);
        transform.rotation = Quaternion.Slerp(
            transform.rotation, spawnRotation, floatBackSpeed * Time.deltaTime);

        if (Vector3.Distance(transform.position, spawnPosition) < 0.01f)
        {
            transform.position = spawnPosition;
            transform.rotation = spawnRotation;
            isFloatingBack = false;
        }
    }

    // ─────────────────────────────────────────
    //  Hand Identification
    // ─────────────────────────────────────────
    private bool IsRightHand(Transform hand)
    {
        if (rightHandController != null && leftHandController != null)
        {
            float dRight = Vector3.Distance(hand.position, rightHandController.position);
            float dLeft = Vector3.Distance(hand.position, leftHandController.position);
            return dRight < dLeft;
        }
        return hand.name.ToLower().Contains("right");
    }

    // ─────────────────────────────────────────
    //  Helpers
    // ─────────────────────────────────────────
    private void SetAxeColor(Color color)
    {
        if (axeRenderer != null)
            axeRenderer.material.color = color;
    }

    void OnDrawGizmosSelected()
    {
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(
            spawnPosition == Vector3.zero ? transform.position : spawnPosition,
            miningRange);
    }
}