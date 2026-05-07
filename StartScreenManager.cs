using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using TMPro;

public class StartScreenManager : MonoBehaviour
{
    [Header("UI Panels")]
    public GameObject storyPanel;
    public GameObject htpPanel;

    [Header("Buttons")]
    public Button nextButton;     // Moves from Story to HTP
    public Button startButton;    // Loads Level 1

    [Header("Status")]
    public TMP_Text statusText;
    
    private PupilBridgeClient pupil;
    private bool hasPressedNext = false;

    void Start()
    {
        pupil = FindObjectOfType<PupilBridgeClient>();
        
        // Initial State: Show Story, Hide HTP
        storyPanel.SetActive(true);
        htpPanel.SetActive(false);

        // Start button is locked until Next is pressed AND Pupil is ready
        if (startButton != null)
            startButton.interactable = false;

        if (nextButton != null)
            nextButton.interactable = true;
    }

    void Update()
    {
        if (pupil == null) return;

        // Logic: Start is active ONLY if we are on the HTP page AND Pupil is synced
        bool isPupilReady = pupil.IsSyncReady;

        if (isPupilReady)
        {
            if (statusText != null) statusText.text = "Connection Ready!";
            
            // Only enable Start if the user has actually viewed the HTP instructions
            if (hasPressedNext && startButton != null && !startButton.interactable)
            {
                startButton.interactable = true;
            }
        }
        else
        {
            if (statusText != null) statusText.text = "Syncing with Laptop...";
            if (startButton != null) startButton.interactable = false;
        }
    }

    // Assign this to your "NEXT" Button in the Inspector
    public void OnNextButtonPressed()
    {
        hasPressedNext = true;

        // Switch Panels
        storyPanel.SetActive(false);
        htpPanel.SetActive(true);

        // Disable Next button as it's no longer needed
        if (nextButton != null)
            nextButton.interactable = false;
            
        Debug.Log("Switched to HTP. Waiting for Pupil Sync to enable Start.");
    }

    // Assign this to your "START" Button in the Inspector
    public void OnContinueButtonPressed()
    {
        SceneManager.LoadScene("Level1", LoadSceneMode.Single);
    }
}