using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

namespace TriangleCheckGui
{
    public partial class TriangleCheckMain : Form
    {
        const string TRI_RIGHT_ANGLE = "משולש ישר זוית";
        const string TRI_NOT_TRIANGLE = "לא משולש";
        const string TRI_ISOSCELES = "משולשש שווה שוקיים";
        const string TRI_SCALENE = "משולש";
        const string TRI_EQUILATERAL = "משולש שווה צלעות";
        const string NEWLINE = "\r\n";
        const string TAB = "\t";
        int allowSize = 0;

        const string DIVIDER = "-----------------------------------------------------";
        public TriangleCheckMain()
        {
            InitializeComponent();
        }

        private void btnCalculate_Click(object sender, EventArgs e)
        {
                byte _a, _b, _c;
                string[] args = {textSideA.Text,txtSideB.Text,txtSideC.Text};
                string results = "השלשה (" +args[2]+","+args[1]+ ","+ args[0] + ") היא:" + NEWLINE;
                bool showException = true;
                if (args[0].Equals(args[1]) && args[1].Equals(args[2]))
                {
                   results += TRI_EQUILATERAL + NEWLINE;
                    showException = false;
                }
                if (args[0].Equals(args[1]) || args[1].Equals(args[2]))
                {
                    results += TRI_ISOSCELES + NEWLINE;
                    showException = false;
                }
                try
                {
                    _a = Convert.ToByte(args[0]);
                    _b = Convert.ToByte(args[1]);
                    _c = Convert.ToByte(args[2]);



                    if (_a <= 0 || _b < 0)
                        results += TRI_NOT_TRIANGLE + NEWLINE;
                    else if (_a + _b < _c || _a + _c < _b)
                        results += TRI_NOT_TRIANGLE + NEWLINE;
                    else if (_a * _a + _b * _b == _c * _c || _b * _b + _c * _c == _a * _a)
                        results += TRI_RIGHT_ANGLE + NEWLINE;
                   else
                        results += TRI_SCALENE + NEWLINE;
                }
                catch (Exception ex)
                {
//                    if (showException) results += ex.GetType().ToString() + " :: " + ex.Message;
                    if (showException) throw ex;
                }
                txtResults.Text = results + NEWLINE + DIVIDER + NEWLINE + txtResults.Text;
        }

        private void btnHelp_Click(object sender, EventArgs e)
        {
            txtResults.Text = "";
            
             
            txtResults.Text = txtResults.Text +"התוכנה בודקת האם קלט של שלושה מספרים מהווה משולש" + NEWLINE;
            txtResults.Text = txtResults.Text +"פלט אפשרי:" + NEWLINE;
            txtResults.Text = txtResults.Text + TAB + TRI_NOT_TRIANGLE + "," + NEWLINE
                                              + TAB + TRI_SCALENE + "," + NEWLINE
                                              + TAB + TRI_ISOSCELES + "," + NEWLINE
                                              + TAB + TRI_EQUILATERAL + "," + NEWLINE
                                              + TAB + TRI_RIGHT_ANGLE + "," + NEWLINE
                                              + TAB + TRI_SCALENE;

        }

        private void CleanInput(int side)
        {
            if (side == 1)
                textSideA.Text = "";
            else if (side == 2)
                txtSideB.Text = "";
            txtSideC.Text = "";
        }

        private void btnCleanData_Click(object sender, EventArgs e)
        {
            txtSideB.Text = "";
            txtSideC.Text = "";
            textSideA.Text = "";
        }

        private void btnCleanResults_Click(object sender, EventArgs e)
        {
            txtResults.Text = "";
        }

        private void btnCleanC_Click(object sender, EventArgs e)
        {
            CleanInput(3);
        }

        private void btnCleanB_Click(object sender, EventArgs e)
        {
            CleanInput(1);
        }

        private void btnCleanA_Click(object sender, EventArgs e)
        {
            CleanInput(2);
        }

        private void btnExit_Click(object sender, EventArgs e)
        {
            DialogResult r = MessageBox.Show("?האם אתה בטוח שברצונך לצאת","אישור יציאה",MessageBoxButtons.YesNo,MessageBoxIcon.Information);
            if (r == DialogResult.No)
                this.Close();
        }

        private void TriangleCheckMain_Resize(object sender, EventArgs e)
        {
            
            if (allowSize%3 == 0)
            {
                
                this.WindowState = FormWindowState.Maximized;
                
            }
            allowSize++;

        }
    }
}