using UnityEngine;

public class PracticeManager : MonoBehaviour
{
    public ForagingUI ui;
    private bool rock0Active = true; // Practice state

    public void ResolvePracticeHit(int rockID) 
    {
        // Check if the player hit the correct "Active" rock
        bool success = (rockID == 0 && rock0Active) || (rockID == 1 && !rock0Active);

        if (success) 
        {
            ui.ShowMessage("Practice Gold +10!", 1.5f);
            rock0Active = !rock0Active; // Swap for practice
        }
        else 
        {
            ui.ShowMessage("Rock Empty! Try the other one.", 1.5f);
        }
    }
}
